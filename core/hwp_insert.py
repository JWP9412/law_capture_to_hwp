"""
만들어진 그림을 한글(HWP) 문서에 넣는 일을 담당한다.

넣을 때 함께 하는 것들:
  - 본문 폭에 맞게 크기 조절 (그림이 찌그러지지 않도록 가로세로 비율 유지)
  - 그림 테두리 0.12mm 검은 실선
  - 그림 위에 캡션 달기 (왼쪽 정렬, 휴먼명조 10pt)

이 파일에서 특히 조심한 두 가지:

  1) 저장은 반드시 임시 폴더를 거친다.
     이 컴퓨터는 회사 PC 라 문서보안 프로그램이 한글의 저장을 막는다.
     바탕화면이나 내 문서에 저장하면 오류 메시지도 없이 조용히 실패한다.
     임시 폴더에는 저장이 되므로, 거기 저장한 뒤 파이썬이 옮겨온다.

  2) pyhwpx 의 move_caption 을 쓰지 않는다.
     그 함수는 캡션을 옮기면서 가운데 정렬을 강제로 걸고,
     문서 안의 모든 캡션을 훑어서 앞서 넣은 그림의 캡션까지 바꿔버린다.
     그림을 여러 장 넣는 이 프로그램에는 맞지 않아 직접 구현했다.
"""
import logging
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

import config
from config import InsertionMode, TextAlignment
from core.errors import HwpAutomationError, HwpSaveBlockedError, PlaceholderNotFoundError

# 우리 한글을 끈 뒤에도 남아 있는지 확인할 때 쓰는 값.
# 종료 직후에는 윈도우 목록이 잠깐 늦게 갱신될 수 있어 한 번 더 기다려 본다.
HWP_QUIT_WAIT_SECONDS = 0.4
HWP_QUIT_RETRY_COUNT = 2

# 한글은 글자 종류별로 글꼴을 따로 관리한다. 글꼴을 바꿀 때 이 전부를 함께 지정해야
# 한글자와 영문자가 서로 다른 글꼴로 나오는 일이 없다.
CHARACTER_SCRIPT_TYPES = (
    "Hangul",  # 한글
    "Latin",  # 영문
    "Hanja",  # 한자
    "Japanese",  # 일본어
    "Other",  # 그 밖의 문자
    "Symbol",  # 기호
    "User",  # 사용자 정의
)

TRUETYPE_FONT_CODE = 1  # 요즘 쓰는 일반적인 글꼴 형식

# 한글은 본문·머리말·캡션 등을 서로 다른 '구역' 으로 나눠 관리한다. 0 번이 본문이다.
MAIN_BODY_AREA_INDEX = 0

# 기존 문서를 열 때 붙이는 조건.
#
# 이걸 빼면 한글이 문서를 잠긴 상태로 연다. 글자는 넣을 수 있지만
# 그림에 캡션을 다는 것 같은 개체 수정이 조용히 실패한다.
# (캡션 부착이 False 를 돌려주고 아무 일도 일어나지 않는다)
OPEN_WITHOUT_LOCK = "lock:false"

ALIGNMENT_COMMANDS = {
    TextAlignment.LEFT: "ParagraphShapeAlignLeft",
    TextAlignment.CENTER: "ParagraphShapeAlignCenter",
}


@dataclass(frozen=True)
class PictureInsertion:
    """
    그림 한 장을 넣을 때 필요한 값들을 한데 묶은 것.

    매개변수로 하나씩 넘기면 여섯 개가 되어 '셋 이하' 원칙을 넘긴다.
    관련된 값끼리 묶어 호출부를 읽기 쉽게 한다.

    caption 이 None 이면 캡션을 달지 않는다.
    should_add_border 가 False 이면 테두리를 그리지 않는다.
    """

    image_path: Path
    caption: str | None
    insertion_mode: InsertionMode
    placeholder: str | None = None
    should_add_border: bool = True


class HwpDocumentEditor:
    """
    한글 문서 하나를 열어놓고 그림을 넣는 작업대.

    그림을 여러 장 넣을 때 한글을 매번 켰다 끄면 몹시 느리므로,
    한 번 열어서 전부 넣고 마지막에 저장한 뒤 닫는다.

    사용 예:
        with open_hwp_document(원본, 결과) as editor:
            editor.insert_picture_with_caption(PictureInsertion(그림1, 캡션1, 방식))
            editor.insert_picture_with_caption(PictureInsertion(그림2, 캡션2, 방식))
    """

    def __init__(self, source_document_path: Path | None, result_path: Path):
        self._source_document_path = source_document_path
        self._result_path = result_path
        self._hwp = None
        self._is_our_own_hwp = False
        # 우리가 새로 켠 한글의 이름표. 종료 후 정말 사라졌는지 확인할 때 쓴다.
        self._our_hwp_instance_names: set[str] = set()
        self._our_document = None

    def __enter__(self) -> "HwpDocumentEditor":
        from pyhwpx import Hwp

        self._prepare_windows_program_control()

        # 한글을 켜기 전에 이미 떠 있던 것들의 이름표를 적어 둔다.
        # 켠 뒤에 새 이름표가 생겼으면 그것이 '우리 한글' 이다.
        # 사용자가 쓰던 한글을 끄지 않으면서도 우리 것은 확실히 끄기 위한 구분이다.
        names_before = _running_hwp_instance_names()

        try:
            # register_module=True 로 두면 한글의 보안 승인 팝업이 뜨지 않는다.
            self._hwp = Hwp(new=True, visible=False, register_module=True)
        except Exception as error:
            raise HwpAutomationError("한글 프로그램 실행", str(error)) from error

        self._our_hwp_instance_names = _running_hwp_instance_names() - names_before
        self._is_our_own_hwp = bool(self._our_hwp_instance_names)

        self._open_our_own_document()
        return self

    def _open_our_own_document(self) -> None:
        """
        작업할 문서를 준비한다.

        한글을 새로 켜면 '빈 문서 1' 이 딸려 온다. 우리가 켠 창은 우리만 쓰므로
        그 문서를 그대로 쓴다. 예전에는 여기서 문서를 하나 더 만들었는데,
        그래서 '빈 문서 1' 과 '빈 문서 2' 가 같이 떠서 사용자를 놀라게 했다.

        다만 우리 창이 아니라 **사용자가 쓰던 한글에 올라탄 경우**에는 이야기가 다르다.
        딸려 온 문서라는 것이 없고, 지금 열려 있는 것은 사용자의 문서다.
        그 문서에 글을 쓰면 남의 작업을 망가뜨리므로 이때만 새 문서를 만든다.
        """
        try:
            if self._source_document_path is not None:
                self._open_source_document()
            elif not self._is_our_own_hwp:
                self._hwp.XHwpDocuments.Add(0)  # 남의 한글이므로 우리 문서를 따로 만든다

            self._our_document = self._hwp.XHwpDocuments.Active_XHwpDocument
        except HwpAutomationError:
            raise
        except Exception as error:
            raise HwpAutomationError("작업할 문서 준비", str(error)) from error

    def _focus_our_document(self) -> None:
        """
        우리 문서를 앞으로 불러온다.

        작업 중간에 사용자가 한글에서 다른 문서를 눌러 볼 수 있다.
        그때 우리가 그 문서에 글을 쓰면 안 되므로, 매번 확인하고 되돌린다.
        """
        if self._our_document is None:
            return
        try:
            self._our_document.SetActive_XHwpDocument()
        except Exception:
            pass  # 문서가 이미 앞에 있으면 실패할 수 있다. 그대로 진행하면 된다.

    def _prepare_windows_program_control(self) -> None:
        """
        윈도우에서 다른 프로그램(한글)을 조작할 수 있도록 준비한다.

        이 준비는 '일을 하는 흐름마다' 한 번씩 해줘야 한다.
        화면은 창이 멈추지 않도록 실제 작업을 별도 흐름에서 돌리는데,
        그 흐름에서 이것을 빠뜨리면 한글을 아예 잡지 못하고 이렇게 실패한다.

            CoInitialize가 호출되지 않았습니다

        명령줄로 실행할 때는 흐름이 하나뿐이라 저절로 준비되어 문제가 드러나지 않았다.
        그래서 화면에서 실행할 때만 실패했다.

        이미 준비된 흐름에서 또 불러도 문제가 없도록 조용히 넘어간다.

        **끝난 뒤에 정리(CoUninitialize)는 하지 않는다.** 그 정리는 이 흐름 전체의
        연결을 끊어버려서, 같은 흐름에서 다른 프로그램을 다루고 있으면 그것까지
        못 쓰게 만든다. 실제로 정리를 넣었더니 사용자가 열어둔 한글을 더 이상
        읽지 못하는 문제가 생겼다.
        흐름이 끝나면 윈도우가 알아서 정리하므로 우리가 할 일이 없다.
        """
        import pythoncom

        try:
            pythoncom.CoInitialize()
        except Exception:
            pass  # 이미 준비돼 있으면 여기로 온다. 그대로 진행하면 된다.

    def _open_source_document(self) -> None:
        """
        그림을 넣을 기존 문서를 연다.

        여기 오는 경로는 반드시 실제로 존재하는 파일이어야 한다.
        빈 경로나 없는 파일을 한글에게 주면 알아듣기 어려운 오류가 난다.
        (실제로 빈 경로가 현재 폴더로 해석되어 'string index out of range' 가 났다)
        """
        document_path = self._source_document_path

        if not document_path.is_file():
            raise HwpAutomationError(
                "기존 문서 열기",
                f"'{document_path}' 파일이 없습니다",
            )

        try:
            self._hwp.open(str(document_path), "HWP", OPEN_WITHOUT_LOCK)
        except Exception as error:
            raise HwpAutomationError(f"'{document_path.name}' 열기", str(error)) from error

    def __exit__(self, exception_type, *_) -> None:
        if self._hwp is None:
            return  # 한글을 잡지도 못하고 실패한 경우. 정리할 것이 없다.

        try:
            if exception_type is None:
                temporary_path = self._save_into_temporary_folder()
            else:
                temporary_path = None
        finally:
            self._quit_hwp()

        # 한글이 완전히 닫힌 뒤에야 파일을 옮길 수 있다.
        # 저장 직후에는 한글이 그 파일을 붙잡고 있어 옮기려 하면 거부당한다.
        if temporary_path is not None:
            self._move_into_place(temporary_path)

    def insert_picture_with_caption(self, insertion: PictureInsertion) -> None:
        """그림 한 장을 (선택적으로) 캡션·테두리와 함께 문서에 넣는다."""
        # 작업 중간에 사용자가 다른 문서를 눌러 볼 수 있으므로 매번 확인한다.
        self._focus_our_document()

        self._move_caret_to_insertion_point(
            insertion.insertion_mode, insertion.placeholder
        )
        picture = self._insert_picture_fitted_to_body_width(insertion.image_path)

        if insertion.caption is not None:
            self._attach_caption(picture, insertion.caption)

        # 테두리와 캡션 위치는 그림 속성이라 같은 설정 묶음으로 다루되,
        # 끈 항목은 건드리지 않는다.
        self._apply_picture_options(
            picture,
            should_add_border=insertion.should_add_border,
            should_place_caption=insertion.caption is not None,
        )

    # -- 아래는 위 네 단계의 세부 내용 --

    def _move_caret_to_insertion_point(
        self, insertion_mode: InsertionMode, placeholder: str | None
    ) -> None:
        """그림을 넣을 자리로 글자 입력 위치를 옮긴다."""
        if insertion_mode is InsertionMode.REPLACE_PLACEHOLDER:
            if not placeholder:
                raise HwpAutomationError("삽입 위치 찾기", "표시 문구가 비어 있습니다")
            if not self._hwp.find(placeholder):
                raise PlaceholderNotFoundError(placeholder, self._result_path)
            self._hwp.Delete()  # 표시 문구를 지우면 그 자리에 입력 위치가 남는다
            return

        # 앞 그림의 캡션을 편집한 뒤라면 글자 입력 위치가 그 캡션 안에 남아 있을 수 있다.
        # 그 상태로 '문서 끝' 을 찾으면 캡션 칸의 끝으로 가버려서
        # 다음 그림이 엉뚱한 자리(앞 그림보다 위)에 들어간다.
        # 그래서 먼저 본문 맨 앞으로 확실히 빠져나온 뒤에 끝으로 이동한다.
        self._hwp.set_pos(MAIN_BODY_AREA_INDEX, 0, 0)
        self._hwp.MoveDocEnd()
        self._hwp.BreakPara()

    def _insert_picture_fitted_to_body_width(self, image_path: Path):
        """
        본문 폭에 맞춰 그림을 넣고, 넣은 그림을 가리키는 표를 돌려준다.

        돌려받은 표를 들고 있어야 나중에 '바로 이 그림' 을 다시 지목할 수 있다.
        그림을 여러 장 넣을 때 이것이 없으면 엉뚱한 그림에 테두리나 캡션이 붙는다.
        (실제로 두 번째 그림의 캡션이 첫 번째 그림에 붙는 일이 있었다)
        """
        self._run_alignment(config.PICTURE_ALIGNMENT)

        try:
            return self._hwp.insert_picture(
                str(image_path),
                embedded=True,  # 그림을 문서 안에 품는다 (파일을 옮겨도 그림이 남도록)
                sizeoption=1,  # 아래에서 지정한 크기를 그대로 쓴다
                width=config.PICTURE_WIDTH_IN_MILLIMETERS,
                height=_calculate_height_keeping_aspect_ratio(image_path),
            )
        except Exception as error:
            raise HwpAutomationError(f"'{image_path.name}' 넣기", str(error)) from error

    def _select_picture(self, picture) -> None:
        """지정한 그림을 선택 상태로 만든다."""
        self._hwp.set_pos_by_set(picture.GetAnchorPos(0))
        self._hwp.find_ctrl()

    def _attach_caption(self, picture, description: str) -> None:
        """
        그림에 캡션을 단다. 번호는 한글이 스스로 매기게 둔다.

        캡션을 달면 한글이 '그림 1' 같은 번호를 자동으로 넣어준다.
        이것은 단순한 글자가 아니라 문서에 놓인 순서를 따라가는 '필드' 라서,
        나중에 그림을 중간에 끼우거나 지워도 번호가 저절로 다시 매겨진다.
        그래서 우리가 숫자를 세어 적어 넣지 않는다.

        대신 번호 앞뒤에 대괄호와 설명만 붙여 '[그림 1] 법령명 제N조 …' 형태를 만든다.
        """
        try:
            self._select_picture(picture)
            self._hwp.ShapeObjAttachCaption()  # 캡션 편집 상태로 들어간다
            self._verify_caret_moved_into_caption()
            self._ensure_caption_number_exists()

            # '그림 1' 앞뒤로 대괄호와 설명을 덧붙인다
            self._hwp.Run("MoveLineBegin")
            self._hwp.insert_text(config.CAPTION_NUMBER_OPENING)  # "["
            self._hwp.Run("MoveLineEnd")
            self._trim_trailing_space_in_caption_line()
            self._hwp.insert_text(config.CAPTION_NUMBER_CLOSING + description)  # "] " + 설명

            self._hwp.Run("SelectAll")
            self._apply_caption_font()
            self._run_alignment(config.CAPTION_ALIGNMENT)
            self._apply_same_as_previous_highlight_in_caption(description)

            self._hwp.Run("Cancel")  # 캡션 편집 상태에서 빠져나온다
        except Exception as error:
            raise HwpAutomationError("캡션 달기", str(error)) from error

    def _apply_same_as_previous_highlight_in_caption(self, description: str) -> None:
        """
        '(앞 개정안과 동일)' 구간만 빨간색 굵게 강조한다.

        캡션 전체를 강조하면 읽기 피로가 커지므로, 같은 개정안임을 알리는
        괄호 문구에만 표시를 준다.
        """
        marker_text = config.SAME_AS_PREVIOUS_VERSION_SUFFIX
        if marker_text not in description:
            return

        suffix_after_marker = description.split(marker_text, maxsplit=1)[1]

        self._hwp.Run("MoveLineEnd")
        for _ in range(len(suffix_after_marker)):
            self._hwp.Run("MovePrevChar")
        for _ in range(len(marker_text)):
            self._hwp.Run("MoveSelPrevChar")

        self._apply_caption_font(
            is_bold=True,
            text_color_rgb=(255, 0, 0),
        )
        self._hwp.Run("Cancel")

    def _trim_trailing_space_in_caption_line(self) -> None:
        """
        캡션 줄 끝의 공백만 지운다. 자동번호 필드는 건드리지 않는다.

        한글이 넣는 번호가 '그림 1 ' 처럼 뒤에 공백이 있으면
        대괄호를 붙였을 때 '[그림 1 ]' 이 된다. 공백만 골라 지운다.
        """
        self._hwp.Run("MovePrevChar")
        self._hwp.Run("MoveSelNextChar")
        if (self._hwp.get_selected_text() or "") == " ":
            self._hwp.Run("Delete")
        else:
            self._hwp.Run("Cancel")
            self._hwp.Run("MoveLineEnd")

    def _ensure_caption_number_exists(self) -> None:
        """
        캡션에 번호가 없으면 한글의 '번호 넣기' 로 넣는다.

        보통 캡션을 달면 한글이 '그림 1' 을 자동으로 넣는다.
        다만 한글 설정에 따라 번호가 비어 있는 채로 열릴 수 있어,
        비어 있으면 직접 번호를 넣는다.
        """
        self._hwp.Run("SelectAll")
        if not (self._hwp.get_selected_text() or "").strip():
            self._hwp.ShapeObjInsertCaptionNum()

    def _apply_picture_options(
        self, picture, should_add_border: bool, should_place_caption: bool
    ) -> None:
        """
        그림에 테두리·캡션 위치를 선택적으로 적용한다.

        한글에서 이런 설정을 바꾸는 방법이 두 가지인데 동작이 전혀 다르다.
          HAction.Run(...Dialog)            -> 설정 창(팝업)이 화면에 실제로 뜬다.
                                               사람이 없으면 거기서 멈춰버린다.
          GetDefault -> 값 수정 -> Execute  -> 팝업 없이 값만 조용히 반영된다.
        당연히 뒤쪽을 쓴다.

        둘 다 끈 경우에는 속성 창을 열 필요가 없으므로 바로 돌아간다.
        """
        if not should_add_border and not should_place_caption:
            return

        try:
            self._select_picture(picture)

            properties = self._hwp.HParameterSet.HShapeObject
            self._hwp.HAction.GetDefault("ShapeObjDialog", properties.HSet)

            if should_add_border:
                properties.ShapeDrawLineAttr.style = self._hwp.hwp_line_type("Solid")
                properties.ShapeDrawLineAttr.Width = self._hwp.mili_to_hwp_unit(
                    config.PICTURE_BORDER_WIDTH_IN_MILLIMETERS
                )
                properties.ShapeDrawLineAttr.Color = self._hwp.rgb_color(
                    *config.PICTURE_BORDER_COLOR
                )

            if should_place_caption:
                properties.ShapeCaption.Side = self._hwp.SideType(config.CAPTION_SIDE)

            self._hwp.HAction.Execute("ShapeObjDialog", properties.HSet)
        except Exception as error:
            raise HwpAutomationError("그림 테두리·캡션 위치", str(error)) from error

    def _verify_caret_moved_into_caption(self) -> None:
        """
        정말로 캡션 안으로 들어왔는지 확인한다.

        캡션이 아니라 본문에 있는 상태로 글자를 넣으면 본문이 망가진다.
        되돌릴 수 없는 동작이므로 그 앞에서 반드시 막는다.
        """
        current_area_index = self._hwp.get_pos()[0]
        if current_area_index == MAIN_BODY_AREA_INDEX:
            raise HwpAutomationError(
                "캡션 편집 상태로 들어가기",
                "그림이 선택되지 않아 캡션을 달 수 없습니다",
            )

    def _apply_caption_font(
        self,
        is_bold: bool = False,
        text_color_rgb: tuple[int, int, int] | None = None,
    ) -> None:
        """
        캡션 글씨를 정해진 글꼴과 크기로 맞춘다.

        pyhwpx 에도 글꼴을 바꾸는 함수가 있지만 쓰지 않는다.
        그 함수는 색상 값의 기본값이 잘못 들어가 있어 호출하면 오류가 난다
        (색을 지정하지 않아도 빈 값을 색으로 해석하려다 실패한다).

        한글은 한글자·영문자·한자 등 글자 종류마다 글꼴을 따로 갖고 있어서
        하나만 바꾸면 나머지가 기본 글꼴로 남는다. 그래서 전부 같이 지정한다.
        """
        properties = self._hwp.HParameterSet.HCharShape
        self._hwp.HAction.GetDefault("CharShape", properties.HSet)

        for script_type in CHARACTER_SCRIPT_TYPES:
            setattr(properties, f"FaceName{script_type}", config.CAPTION_FONT_NAME)
            setattr(properties, f"FontType{script_type}", TRUETYPE_FONT_CODE)

        properties.Height = self._hwp.point_to_hwp_unit(config.CAPTION_FONT_SIZE_IN_POINTS)
        properties.Bold = 1 if is_bold else 0
        if text_color_rgb is not None:
            properties.TextColor = self._hwp.rgb_color(*text_color_rgb)
        self._hwp.HAction.Execute("CharShape", properties.HSet)

    def _run_alignment(self, alignment: TextAlignment) -> None:
        self._hwp.HAction.Run(ALIGNMENT_COMMANDS[alignment])

    def _save_into_temporary_folder(self) -> Path:
        """
        문서를 임시 폴더에 저장하고 그 위치를 돌려준다.

        한글에게 바탕화면이나 내 문서 경로를 직접 주면 회사 보안 프로그램이 막는다.
        오류도 없이 그냥 파일이 안 만들어지므로, 막히지 않는 임시 폴더를 거친다.
        """
        temporary_path = Path(tempfile.gettempdir()) / f"lawcapture_{uuid.uuid4().hex}.hwp"

        was_saved = self._hwp.save_as(str(temporary_path), format="HWP")
        if not was_saved or not temporary_path.exists():
            raise HwpSaveBlockedError(temporary_path)

        return temporary_path

    def _move_into_place(self, temporary_path: Path) -> None:
        self._result_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temporary_path), str(self._result_path))

    def _quit_hwp(self) -> None:
        """
        작업을 마치고 한글을 정리한다. **사용자가 쓰던 문서는 절대 건드리지 않는다.**

        우리가 켠 한글이면 프로그램을 바로 끈다.
        예전에 문서를 먼저 닫고 나서 종료를 요청했더니, 문서가 하나도 없는
        상태에서는 종료 요청이 먹지 않아 창 없는 한글이 계속 남았다.
        저장은 이미 끝난 뒤이므로 '저장할까요' 창도 뜨지 않는다.
        그래서 문서 닫기를 건너뛰고 바로 종료한다.

        남의 한글에 올라탄 경우에만 우리 문서만 닫고, 프로그램은 절대 끄지 않는다.
        """
        if not self._is_our_own_hwp:
            # 사용자가 쓰던 한글에 올라탄 경우다. 절대 끄지 않는다.
            self._close_our_document()
            self._hwp = None
            return

        # 우리 인스턴스: 문서를 따로 닫지 말고 바로 종료한다.
        self._request_hwp_quit_until_gone()
        self._our_document = None
        self._hwp = None

    def _request_hwp_quit_until_gone(self) -> None:
        """
        우리 한글에 종료를 요청하고, 정말 사라졌는지 확인한다.

        한 번에 안 꺼질 수 있어 짧게 기다린 뒤 한 번 더 시도한다.
        그래도 남으면 조용히 넘기지 않고 기록해 둔다 — 다음 실행에서
        유령 한글 때문에 저장이 실패하는 원인을 찾기 위해서다.
        """
        for attempt in range(1, HWP_QUIT_RETRY_COUNT + 1):
            try:
                self._hwp.quit()
            except Exception as error:
                logging.warning(
                    "한글 종료 요청 실패 (시도 %s/%s): %s",
                    attempt,
                    HWP_QUIT_RETRY_COUNT,
                    error,
                )

            time.sleep(HWP_QUIT_WAIT_SECONDS)
            remaining = self._our_hwp_instance_names & _running_hwp_instance_names()
            if not remaining:
                return

        remaining = self._our_hwp_instance_names & _running_hwp_instance_names()
        if remaining:
            logging.warning(
                "우리가 켠 한글이 종료되지 않고 남았습니다: %s",
                ", ".join(sorted(remaining)),
            )

    def _close_our_document(self) -> None:
        """우리가 만든 문서 하나만 닫는다. 남의 한글에 올라탔을 때만 쓴다."""
        if self._our_document is None:
            return
        try:
            self._our_document.Close(False)  # False = 변경사항 묻지 않고 닫기
        except Exception:
            pass
        finally:
            self._our_document = None


def _running_hwp_instance_names() -> set[str]:
    """
    지금 떠 있는 한글들의 이름표를 모아 온다. (건드리지 않고 보기만 한다)

    윈도우는 실행 중인 프로그램들의 이름표를 한 곳에 모아 두는데,
    한글은 거기에 '!HwpObject.110.1' 처럼 번호가 붙은 이름으로 올라간다.
    한글을 켜기 전후로 이 목록을 견주어 보면 어느 것이 우리가 켠 것인지 알 수 있다.

    이 구분이 왜 중요한가: 사용자가 다른 문서로 일하는 중일 수 있는데
    그 한글을 끄면 작업이 통째로 날아간다. 반대로 우리 것을 안 끄면
    보이지 않는 한글이 실행할 때마다 하나씩 쌓인다. 둘 다 피해야 한다.
    """
    import pythoncom

    try:
        context = pythoncom.CreateBindCtx(0)
        return {
            name
            for name in (
                moniker.GetDisplayName(context, moniker)
                for moniker in pythoncom.GetRunningObjectTable().EnumRunning()
            )
            if name.startswith("!HwpObject.")
        }
    except Exception:
        # 확인에 실패하면 빈 목록으로 본다. 그러면 '우리 것이 아니다' 로 판단되어
        # 아무것도 끄지 않는다. 남의 한글을 끄는 것보다 안전한 쪽이다.
        return set()


def _calculate_height_keeping_aspect_ratio(image_path: Path) -> float:
    """정해진 가로 폭에 맞출 때 그림이 찌그러지지 않도록 세로 길이를 계산한다."""
    with Image.open(image_path) as image:
        return config.PICTURE_WIDTH_IN_MILLIMETERS * image.height / image.width


def open_hwp_document(source_document_path: Path | None, result_path: Path):
    """
    한글 문서를 열고, 작업이 끝나면 저장한 뒤 닫는다.

    source_document_path 를 주지 않으면 빈 문서에서 시작한다.
    작업 도중 오류가 나면 저장하지 않는다 (반쯤 만들어진 문서를 남기지 않기 위해).
    """
    return HwpDocumentEditor(source_document_path, result_path)
