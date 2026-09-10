from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .ade import PARIS_TIMEZONE, AdeEvent, events_for_week

WIDTH = 1400
PADDING = 64
HEADER_HEIGHT = 205
DAY_HEADER_HEIGHT = 76
DAY_PADDING = 32
DAY_GAP = 24
EVENT_GAP = 18
EMPTY_DAY_HEIGHT = 74
EVENT_MIN_HEIGHT = 140
EVENT_PADDING = 28
TITLE_MAX_LINES = 2

BACKGROUND = "#101827"
CARD = "#F8FAFC"
CARD_TEXT = "#172033"
MUTED_TEXT = "#64748B"
ACCENT = "#5576F2"
ACCENT_LIGHT = "#E7EDFF"
EVENT_CARD = "#EEF3FF"
EVENT_BORDER = "#C8D5FF"
WHITE = "#FFFFFF"

FONT_DIRECTORY = Path("/usr/share/fonts/truetype/dejavu")

WEEKDAYS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi")
MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


@dataclass(frozen=True, slots=True)
class _EventLayout:
    event: AdeEvent
    title_lines: tuple[str, ...]
    height: int


def render_week_schedule(events: list[AdeEvent], *, reference: date | None = None) -> bytes:
    reference = reference or datetime.now(PARIS_TIMEZONE).date()
    display_reference = _next_school_day(reference)
    title_font = _font("DejaVuSans-Bold.ttf", 32)
    event_title_font = _font("DejaVuSans.ttf", 30)
    event_time_font = _font("DejaVuSans-Bold.ttf", 28)
    title_width = WIDTH - (PADDING * 2) - (EVENT_PADDING * 2)
    display_days = _remaining_weekdays(display_reference)

    events_by_day: dict[date, list[AdeEvent]] = defaultdict(list)
    for event in events_for_week(events, reference=display_reference):
        events_by_day[event.starts_at.date()].append(event)

    layouts = [
        _day_layout(
            events_by_day[current_day],
            event_title_font,
            title_width,
        )
        for current_day in display_days
    ]
    image_height = (
        PADDING
        + HEADER_HEIGHT
        + sum(DAY_HEADER_HEIGHT + DAY_PADDING * 2 + _layout_height(layout) for layout in layouts)
        + DAY_GAP * max(0, len(display_days) - 1)
        + 66
    )
    image = Image.new("RGB", (WIDTH, image_height), BACKGROUND)
    draw = ImageDraw.Draw(image)

    _draw_header(draw, display_days[0], display_days[-1])
    current_y = PADDING + HEADER_HEIGHT
    for current_day, layout in zip(display_days, layouts, strict=True):
        card_height = DAY_HEADER_HEIGHT + DAY_PADDING * 2 + _layout_height(layout)
        _draw_day(
            draw,
            x=PADDING,
            y=current_y,
            width=WIDTH - PADDING * 2,
            height=card_height,
            weekday=WEEKDAYS[current_day.weekday()],
            current_day=current_day,
            is_today=current_day == display_reference,
            layout=layout,
            day_font=title_font,
            time_font=event_time_font,
            event_title_font=event_title_font,
        )
        current_y += card_height + DAY_GAP

    footer_font = _font("DejaVuSans.ttf", 22)
    footer = f"Données ADE - actualisées à {datetime.now(PARIS_TIMEZONE):%H:%M}"
    draw.text((PADDING, image_height - 48), footer, font=footer_font, fill="#A9B8D1")

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def schedule_image_filename(*, reference: date | None = None) -> str:
    reference = reference or datetime.now(PARIS_TIMEZONE).date()
    return f"planning-ade-{reference:%Y-%m-%d}.png"


def _day_layout(
    events: list[AdeEvent], event_title_font: ImageFont.FreeTypeFont, title_width: int
) -> tuple[_EventLayout, ...]:
    if not events:
        return ()
    layouts = []
    title_line_height = _line_height(event_title_font)
    for event in events:
        title_lines = tuple(_wrap_text(event.title, event_title_font, title_width, TITLE_MAX_LINES))
        height = max(
            EVENT_MIN_HEIGHT,
            EVENT_PADDING * 2
            + _line_height(_font("DejaVuSans-Bold.ttf", 28))
            + 14
            + title_line_height * len(title_lines),
        )
        layouts.append(_EventLayout(event=event, title_lines=title_lines, height=height))
    return tuple(layouts)


def _layout_height(layout: tuple[_EventLayout, ...]) -> int:
    if not layout:
        return EMPTY_DAY_HEIGHT
    return sum(event_layout.height for event_layout in layout) + EVENT_GAP * (len(layout) - 1)


def _next_school_day(reference: date) -> date:
    if reference.weekday() >= len(WEEKDAYS):
        return reference + timedelta(days=7 - reference.weekday())
    return reference


def _remaining_weekdays(reference: date) -> tuple[date, ...]:
    return tuple(
        reference + timedelta(days=offset) for offset in range(len(WEEKDAYS) - reference.weekday())
    )


def _draw_header(draw: ImageDraw.ImageDraw, first_day: date, last_day: date) -> None:
    title_font = _font("DejaVuSans-Bold.ttf", 58)
    subtitle_font = _font("DejaVuSans.ttf", 31)
    draw.rounded_rectangle((PADDING, PADDING, PADDING + 10, PADDING + 126), radius=5, fill=ACCENT)
    draw.text((PADDING + 34, PADDING - 2), "Planning des chenapans", font=title_font, fill=WHITE)
    subtitle = f"Du {_format_date(first_day)} au {_format_date(last_day, year=True)}"
    draw.text((PADDING + 38, PADDING + 79), subtitle, font=subtitle_font, fill="#C9D6EE")


def _draw_day(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    weekday: str,
    current_day: date,
    is_today: bool,
    layout: tuple[_EventLayout, ...],
    day_font: ImageFont.FreeTypeFont,
    time_font: ImageFont.FreeTypeFont,
    event_title_font: ImageFont.FreeTypeFont,
) -> None:
    draw.rounded_rectangle((x, y, x + width, y + height), radius=26, fill=CARD)
    header_color = ACCENT if is_today else ACCENT_LIGHT
    header_text_color = WHITE if is_today else CARD_TEXT
    draw.rounded_rectangle(
        (x, y, x + width, y + DAY_HEADER_HEIGHT),
        radius=26,
        fill=header_color,
    )
    draw.rectangle((x, y + 34, x + width, y + DAY_HEADER_HEIGHT), fill=header_color)
    draw.text(
        (x + DAY_PADDING, y + 18),
        f"{weekday} {_format_date(current_day)}",
        font=day_font,
        fill=header_text_color,
    )

    content_y = y + DAY_HEADER_HEIGHT + DAY_PADDING
    if not layout:
        empty_font = _font("DejaVuSans-Oblique.ttf", 27)
        draw.text((x + DAY_PADDING, content_y + 4), "Aucun cours", font=empty_font, fill=MUTED_TEXT)
        return

    content_width = width - DAY_PADDING * 2
    for index, event_layout in enumerate(layout):
        _draw_event(
            draw,
            x=x + DAY_PADDING,
            y=content_y,
            width=content_width,
            layout=event_layout,
            time_font=time_font,
            title_font=event_title_font,
        )
        content_y += event_layout.height
        if index < len(layout) - 1:
            content_y += EVENT_GAP


def _draw_event(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    layout: _EventLayout,
    time_font: ImageFont.FreeTypeFont,
    title_font: ImageFont.FreeTypeFont,
) -> None:
    event = layout.event
    draw.rounded_rectangle(
        (x, y, x + width, y + layout.height),
        radius=18,
        fill=EVENT_CARD,
        outline=EVENT_BORDER,
        width=2,
    )
    draw.rounded_rectangle((x, y, x + 9, y + layout.height), radius=4, fill=ACCENT)
    time = f"{event.starts_at:%H:%M} - {event.ends_at:%H:%M}"
    text_x = x + EVENT_PADDING
    text_y = y + EVENT_PADDING - 2
    draw.text((text_x, text_y), time, font=time_font, fill=ACCENT)

    if event.location:
        _draw_location(draw, x + width - EVENT_PADDING, text_y, event.location, time_font)

    draw.multiline_text(
        (text_x, text_y + _line_height(time_font) + 14),
        "\n".join(layout.title_lines),
        font=title_font,
        fill=CARD_TEXT,
        spacing=6,
    )


def _draw_location(
    draw: ImageDraw.ImageDraw, right_x: int, y: int, location: str, font: ImageFont.FreeTypeFont
) -> None:
    padding_x = 15
    text_box = draw.textbbox((0, 0), location, font=font)
    badge_width = text_box[2] - text_box[0] + padding_x * 2
    badge_height = _line_height(font) + 12
    left_x = right_x - badge_width
    draw.rounded_rectangle(
        (left_x, y - 2, right_x, y - 2 + badge_height), radius=badge_height // 2, fill=ACCENT
    )
    draw.text((left_x + padding_x, y), location, font=font, fill=WHITE)


def _wrap_text(
    value: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int
) -> list[str]:
    words = value.split()
    if not words:
        return ["Cours sans titre"]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_width(candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return lines
    shortened = lines[:max_lines]
    shortened[-1] = _ellipsis(shortened[-1], font, max_width)
    return shortened


def _ellipsis(value: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    suffix = "..."
    while value and _text_width(f"{value}{suffix}", font) > max_width:
        value = value[:-1].rstrip()
    return f"{value}{suffix}"


def _font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_DIRECTORY / filename, size)
    except OSError:
        return ImageFont.load_default(size=size)


def _format_date(value: date, *, year: bool = False) -> str:
    suffix = f" {value.year}" if year else ""
    return f"{value.day} {MONTHS[value.month - 1]}{suffix}"


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    bounding_box = font.getbbox("Ag")
    return bounding_box[3] - bounding_box[1]


def _text_width(value: str, font: ImageFont.FreeTypeFont) -> float:
    return font.getlength(value)
