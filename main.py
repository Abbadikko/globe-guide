"""
main.py
Globe Guide — Kivy Android App
Screens: Search, Guide, Compare, Checklist, Saved
"""

import threading
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window

from api_client import CountryAPIClient, load_all_countries
from ai_guide import RelocationGuide, CountryComparator
from guide_saver import save_guide, list_saved_guides, load_saved_guide
from models import Country

# ── Palette ──────────────────────────────────
INK        = (0.05, 0.07, 0.09, 1)
PAPER      = (0.97, 0.96, 0.95, 1)
ACCENT     = (0.15, 0.39, 0.92, 1)
ACCENT2    = (0.20, 0.50, 1.00, 1)
GOLD       = (0.85, 0.47, 0.03, 1)
WHITE      = (1, 1, 1, 1)
LIGHT_GREY = (0.93, 0.93, 0.93, 1)
MID_GREY   = (0.42, 0.45, 0.50, 1)
SUCCESS    = (0.02, 0.59, 0.41, 1)
DANGER     = (0.86, 0.20, 0.18, 1)


# ── Reusable Widgets ─────────────────────────

def make_label(text, size=14, bold=False, color=INK, halign="left",
               wrap=True, italic=False):
    lbl = Label(
        text=text,
        font_size=dp(size),
        bold=bold,
        italic=italic,
        color=color,
        halign=halign,
        valign="top",
        size_hint_y=None,
        markup=True,
    )
    if wrap:
        lbl.bind(width=lambda *a: setattr(lbl, "text_size", (lbl.width, None)))
        lbl.bind(texture_size=lambda *a: setattr(lbl, "height", lbl.texture_size[1]))
    return lbl


def make_button(text, bg=ACCENT, fg=WHITE, height=48, on_press=None):
    btn = Button(
        text=text,
        font_size=dp(14),
        bold=True,
        color=fg,
        background_normal="",
        background_color=bg,
        size_hint=(1, None),
        height=dp(height),
    )
    if on_press:
        btn.bind(on_press=on_press)
    return btn


def make_input(hint, password=False, height=44):
    return TextInput(
        hint_text=hint,
        password=password,
        multiline=False,
        font_size=dp(14),
        size_hint=(1, None),
        height=dp(height),
        padding=[dp(10), dp(10)],
    )


def scroll_wrap(widget, padding=12):
    sv = ScrollView(size_hint=(1, 1))
    box = BoxLayout(orientation="vertical",
                    size_hint_y=None,
                    padding=dp(padding),
                    spacing=dp(8))
    box.bind(minimum_height=box.setter("height"))
    box.add_widget(widget)
    sv.add_widget(box)
    return sv


def stat_card(label, value):
    box = BoxLayout(orientation="vertical",
                    size_hint=(1, None),
                    height=dp(60),
                    padding=dp(8),
                    spacing=dp(2))
    with box.canvas.before:
        from kivy.graphics import Color, RoundedRectangle
        Color(*LIGHT_GREY)
        box._rect = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(8)])
    box.bind(pos=lambda *a: setattr(box._rect, "pos", box.pos))
    box.bind(size=lambda *a: setattr(box._rect, "size", box.size))
    box.add_widget(make_label(label.upper(), size=10, color=MID_GREY, bold=True))
    box.add_widget(make_label(value, size=13, bold=True))
    return box


def show_popup(title, message, error=False):
    color = DANGER if error else SUCCESS
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    content.add_widget(make_label(message, size=13, wrap=True))
    btn = make_button("OK", bg=color)
    content.add_widget(btn)
    popup = Popup(title=title, content=content,
                  size_hint=(0.85, None), height=dp(220),
                  title_color=WHITE, title_size=dp(15),
                  separator_color=color)
    btn.bind(on_press=popup.dismiss)
    popup.open()


def nav_bar(screen_manager, current):
    bar = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(2))
    pages = [
        ("🔍", "search"), ("⚖️", "compare"),
        ("✅", "checklist"), ("📂", "saved"), ("⚙️", "settings"),
    ]
    for icon, name in pages:
        bg = ACCENT if name == current else (0.20, 0.22, 0.26, 1)
        btn = Button(text=icon, font_size=dp(22),
                     background_normal="", background_color=bg,
                     size_hint=(1, 1))
        btn.bind(on_press=lambda b, n=name: setattr(screen_manager, "current", n))
        bar.add_widget(btn)
    return bar


# ── App State ────────────────────────────────

class AppState:
    """Singleton carrying shared state across screens."""
    gemini_key: str = ""
    all_countries: list = []
    current_country: Country = None
    compare_a: Country = None
    compare_b: Country = None
    guide_client: RelocationGuide = None
    api_client: CountryAPIClient = CountryAPIClient()

    @classmethod
    def get_guide(cls):
        if cls.gemini_key and (
            cls.guide_client is None
            or not hasattr(cls.guide_client, "_key")
            or cls.guide_client._key != cls.gemini_key
        ):
            cls.guide_client = RelocationGuide(cls.gemini_key)
            cls.guide_client._key = cls.gemini_key
        return cls.guide_client


# ── Screens ──────────────────────────────────

class SearchScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)

        # Header
        header = BoxLayout(size_hint=(1, None), height=dp(56),
                           padding=[dp(16), 0])
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*INK)
            header._bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(header._bg, "pos", header.pos))
        header.bind(size=lambda *a: setattr(header._bg, "size", header.size))
        header.add_widget(make_label("🌍  Globe Guide", size=18,
                                     bold=True, color=WHITE))
        root.add_widget(header)

        # Search area
        search_box = BoxLayout(orientation="vertical",
                               size_hint=(1, None), height=dp(112),
                               padding=dp(12), spacing=dp(8))
        with search_box.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*PAPER)
            search_box._bg = Rectangle(pos=search_box.pos, size=search_box.size)
        search_box.bind(pos=lambda *a: setattr(search_box._bg, "pos", search_box.pos))
        search_box.bind(size=lambda *a: setattr(search_box._bg, "size", search_box.size))

        self.search_input = make_input("Search a country e.g. Nigeria, Japan…")
        self.search_input.bind(on_text_validate=lambda *a: self._do_search())
        search_box.add_widget(self.search_input)
        search_box.add_widget(make_button("Search 🔍", on_press=lambda *a: self._do_search()))
        root.add_widget(search_box)

        # Results scroll
        self.result_box = BoxLayout(orientation="vertical",
                                    size_hint_y=None, spacing=dp(8),
                                    padding=[dp(12), dp(8)])
        self.result_box.bind(minimum_height=self.result_box.setter("height"))
        sv = ScrollView(size_hint=(1, 1))
        sv.add_widget(self.result_box)
        root.add_widget(sv)

        root.add_widget(nav_bar(None, "search"))
        self._nav_bar_ref = root.children[0]
        self.add_widget(root)
        self._root = root

    def on_enter(self):
        # Patch nav bar with real screen manager
        self._root.remove_widget(self._nav_bar_ref)
        bar = nav_bar(self.manager, "search")
        self._root.add_widget(bar)
        self._nav_bar_ref = bar

        if not AppState.all_countries:
            self._show_status("Loading country database…")
            threading.Thread(target=self._load_countries, daemon=True).start()

    def _load_countries(self):
        try:
            AppState.all_countries = load_all_countries()
            Clock.schedule_once(lambda *a: self._show_status(
                f"✅ {len(AppState.all_countries)} countries loaded. Search above!"))
        except Exception as e:
            Clock.schedule_once(lambda *a: self._show_status(f"❌ {e}", error=True))

    def _show_status(self, msg, error=False):
        self.result_box.clear_widgets()
        self.result_box.add_widget(
            make_label(msg, size=13, color=DANGER if error else MID_GREY,
                       italic=True))

    def _do_search(self):
        query = self.search_input.text.strip()
        if not query:
            return
        self._show_status("Searching…")
        threading.Thread(target=self._search_thread, args=(query,), daemon=True).start()

    def _search_thread(self, query):
        try:
            results = AppState.api_client.search(query, AppState.all_countries)
            Clock.schedule_once(lambda *a: self._show_results(results))
        except Exception as e:
            Clock.schedule_once(lambda *a: self._show_status(f"⚠️ {e}", error=True))

    def _show_results(self, results):
        self.result_box.clear_widgets()
        for country in results:
            btn = make_button(
                f"{country.flag_emoji}  {country.name}  —  {country.capital}",
                bg=INK, height=52
            )
            btn.bind(on_press=lambda b, c=country: self._select(c))
            self.result_box.add_widget(btn)

    def _select(self, country):
        AppState.current_country = country
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "detail"


class DetailScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

    def on_enter(self):
        self.clear_widgets()
        c = AppState.current_country
        if not c:
            self.add_widget(make_label("No country selected.", size=14))
            return
        self._build(c)

    def _build(self, c: Country):
        root = BoxLayout(orientation="vertical", spacing=0)

        # Header
        header = BoxLayout(size_hint=(1, None), height=dp(56),
                           padding=[dp(12), 0], spacing=dp(8))
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*INK)
            header._bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(header._bg, "pos", header.pos))
        header.bind(size=lambda *a: setattr(header._bg, "size", header.size))
        back_btn = Button(text="◀", font_size=dp(18), bold=True,
                          color=WHITE, background_normal="",
                          background_color=INK,
                          size_hint=(None, 1), width=dp(40))
        back_btn.bind(on_press=lambda *a: self._go_back())
        header.add_widget(back_btn)
        header.add_widget(make_label(
            f"{c.flag_emoji}  {c.name}", size=16, bold=True, color=WHITE))
        root.add_widget(header)

        # Scrollable content
        sv = ScrollView(size_hint=(1, 1))
        content = BoxLayout(orientation="vertical",
                            size_hint_y=None, spacing=dp(10),
                            padding=dp(14))
        content.bind(minimum_height=content.setter("height"))

        # Stats grid
        grid = GridLayout(cols=2, size_hint=(1, None),
                          spacing=dp(8), height=dp(200))
        grid.bind(minimum_height=grid.setter("height"))
        stats = [
            ("Capital", c.capital),
            ("Region", c.region),
            ("Population", f"{c.population:,}" if c.population else "N/A"),
            ("Area", f"{c.area:,.0f} km²" if c.area else "N/A"),
            ("Calling Code", c.calling_code),
            ("ISO Code", c.iso2 or "N/A"),
        ]
        for label, value in stats:
            grid.add_widget(stat_card(label, value or "N/A"))
        content.add_widget(grid)

        # Languages / currencies
        content.add_widget(make_label("🗣 Languages", size=12,
                                       bold=True, color=MID_GREY))
        content.add_widget(make_label(
            ", ".join(c.languages) if c.languages else "N/A", size=13))
        content.add_widget(make_label("💰 Currencies", size=12,
                                       bold=True, color=MID_GREY))
        content.add_widget(make_label(
            ", ".join(c.currencies), size=13))

        content.add_widget(make_label("─" * 60, size=10, color=LIGHT_GREY))

        # Action buttons
        content.add_widget(make_label("AI Features", size=13,
                                       bold=True, color=MID_GREY))
        content.add_widget(make_button(
            "📖 Generate Relocation Guide",
            on_press=lambda *a: self._open_guide("relocation")))
        content.add_widget(make_button(
            "✈️ Generate Travel Guide",
            bg=GOLD,
            on_press=lambda *a: self._open_guide("travel")))
        content.add_widget(make_button(
            "✅ Generate Travel Checklist",
            bg=SUCCESS,
            on_press=lambda *a: self._open_checklist()))
        content.add_widget(make_button(
            "⚖️ Use in Comparison",
            bg=(0.25, 0.27, 0.32, 1),
            on_press=lambda *a: self._use_in_compare()))

        sv.add_widget(content)
        root.add_widget(sv)

        bar = nav_bar(self.manager, "search")
        root.add_widget(bar)
        self.add_widget(root)

    def _go_back(self):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "search"

    def _open_guide(self, purpose):
        AppState._guide_purpose = purpose
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "guide"

    def _open_checklist(self):
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "checklist"

    def _use_in_compare(self):
        if AppState.compare_a is None:
            AppState.compare_a = AppState.current_country
            show_popup("Set as Country A",
                       f"{AppState.current_country.name} set as Country A.\nNow search for Country B.")
        else:
            AppState.compare_b = AppState.current_country
            self.manager.current = "compare"


class GuideScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

    def on_enter(self):
        self.clear_widgets()
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)

        # Header
        header = BoxLayout(size_hint=(1, None), height=dp(56),
                           padding=[dp(12), 0], spacing=dp(8))
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*INK)
            header._bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(header._bg, "pos", header.pos))
        header.bind(size=lambda *a: setattr(header._bg, "size", header.size))
        back = Button(text="◀", font_size=dp(18), bold=True, color=WHITE,
                      background_normal="", background_color=INK,
                      size_hint=(None, 1), width=dp(40))
        back.bind(on_press=lambda *a: self._go_back())
        header.add_widget(back)
        purpose = getattr(AppState, "_guide_purpose", "relocation")
        c = AppState.current_country
        title = f"{'📖' if purpose == 'relocation' else '✈️'} {c.name if c else ''} Guide"
        header.add_widget(make_label(title, size=15, bold=True, color=WHITE))
        root.add_widget(header)

        # Content area
        sv = ScrollView(size_hint=(1, 1))
        self._content = BoxLayout(orientation="vertical",
                                   size_hint_y=None, spacing=dp(10),
                                   padding=dp(14))
        self._content.bind(minimum_height=self._content.setter("height"))

        self._status = make_label("Generating guide, please wait…",
                                   size=13, color=MID_GREY, italic=True)
        self._content.add_widget(self._status)
        sv.add_widget(self._content)
        root.add_widget(sv)

        bar = nav_bar(self.manager, "search")
        root.add_widget(bar)
        self.add_widget(root)
        self._root = root

        threading.Thread(target=self._generate, daemon=True).start()

    def _generate(self):
        guide = AppState.get_guide()
        if not guide:
            Clock.schedule_once(lambda *a: self._show(
                None, "⚙️ No Gemini API key. Add it in Settings."))
            return
        try:
            purpose = getattr(AppState, "_guide_purpose", "relocation")
            text = guide.generate(AppState.current_country, purpose)
            Clock.schedule_once(lambda *a: self._show(text))
        except Exception as e:
            Clock.schedule_once(lambda *a: self._show(None, f"❌ {e}"))

    def _show(self, text, error=None):
        self._content.clear_widgets()
        if error:
            self._content.add_widget(make_label(error, size=13, color=DANGER))
            return
        self._guide_text = text
        self._content.add_widget(make_label(text, size=13))
        self._content.add_widget(make_button(
            "💾 Save Guide to File",
            bg=SUCCESS,
            on_press=lambda *a: self._save()))

    def _save(self):
        c = AppState.current_country
        purpose = getattr(AppState, "_guide_purpose", "relocation")
        fname = f"{c.name}_{purpose}_guide.txt".replace(" ", "_")
        try:
            msg = save_guide(self._guide_text, fname)
            show_popup("Saved", f"{msg}\n→ saved_guides/{fname}")
        except Exception as e:
            show_popup("Error", str(e), error=True)

    def _go_back(self):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "detail"


class ChecklistScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

    def on_enter(self):
        self.clear_widgets()
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)

        header = BoxLayout(size_hint=(1, None), height=dp(56),
                           padding=[dp(12), 0], spacing=dp(8))
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*INK)
            header._bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(header._bg, "pos", header.pos))
        header.bind(size=lambda *a: setattr(header._bg, "size", header.size))
        back = Button(text="◀", font_size=dp(18), bold=True, color=WHITE,
                      background_normal="", background_color=INK,
                      size_hint=(None, 1), width=dp(40))
        back.bind(on_press=lambda *a: self._go_back())
        header.add_widget(back)
        c = AppState.current_country
        header.add_widget(make_label(
            f"✅ Checklist — {c.name if c else ''}",
            size=15, bold=True, color=WHITE))
        root.add_widget(header)

        # Purpose picker
        pick_box = BoxLayout(size_hint=(1, None), height=dp(50),
                             padding=[dp(12), dp(6)], spacing=dp(8))
        self.purpose_spinner = Spinner(
            text="vacation",
            values=["vacation", "study", "work", "long-term relocation"],
            font_size=dp(13),
            size_hint=(1, 1),
        )
        pick_box.add_widget(self.purpose_spinner)
        pick_box.add_widget(make_button(
            "Generate", height=38,
            on_press=lambda *a: self._generate()))
        root.add_widget(pick_box)

        sv = ScrollView(size_hint=(1, 1))
        self._content = BoxLayout(orientation="vertical",
                                   size_hint_y=None, spacing=dp(8),
                                   padding=dp(14))
        self._content.bind(minimum_height=self._content.setter("height"))
        self._status = make_label("Choose a purpose and tap Generate.",
                                   size=13, color=MID_GREY, italic=True)
        self._content.add_widget(self._status)
        sv.add_widget(self._content)
        root.add_widget(sv)

        bar = nav_bar(self.manager, "checklist")
        root.add_widget(bar)
        self.add_widget(root)

    def _generate(self):
        guide = AppState.get_guide()
        if not guide:
            show_popup("API Key Missing",
                       "Add your Gemini API key in Settings.", error=True)
            return
        self._content.clear_widgets()
        self._content.add_widget(make_label(
            "Generating checklist…", size=13, color=MID_GREY, italic=True))
        purpose = self.purpose_spinner.text
        threading.Thread(
            target=self._run, args=(guide, purpose), daemon=True).start()

    def _run(self, guide, purpose):
        try:
            text = guide.generate_checklist(AppState.current_country, purpose)
            Clock.schedule_once(lambda *a: self._show(text, purpose))
        except Exception as e:
            Clock.schedule_once(lambda *a: self._show(None, error=str(e)))

    def _show(self, text, purpose="", error=None):
        self._content.clear_widgets()
        if error:
            self._content.add_widget(make_label(f"❌ {error}", size=13, color=DANGER))
            return
        self._checklist_text = text
        self._content.add_widget(make_label(text, size=13))
        self._content.add_widget(make_button(
            "💾 Save Checklist to File",
            bg=SUCCESS,
            on_press=lambda *a: self._save(purpose)))

    def _save(self, purpose):
        c = AppState.current_country
        fname = f"{c.name}_{purpose}_checklist.txt".replace(" ", "_")
        try:
            msg = save_guide(self._checklist_text, fname)
            show_popup("Saved", f"{msg}\n→ saved_guides/{fname}")
        except Exception as e:
            show_popup("Error", str(e), error=True)

    def _go_back(self):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "detail"


class CompareScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)

        header = BoxLayout(size_hint=(1, None), height=dp(56),
                           padding=[dp(16), 0])
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*INK)
            header._bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(header._bg, "pos", header.pos))
        header.bind(size=lambda *a: setattr(header._bg, "size", header.size))
        header.add_widget(make_label(
            "⚖️  Compare Countries", size=17, bold=True, color=WHITE))
        root.add_widget(header)

        sv = ScrollView(size_hint=(1, 1))
        self._content = BoxLayout(orientation="vertical",
                                   size_hint_y=None, spacing=dp(10),
                                   padding=dp(14))
        self._content.bind(minimum_height=self._content.setter("height"))

        self._content.add_widget(make_label(
            "Search a country, open its detail, and tap\n"
            "[b]Use in Comparison[/b] to set Country A and Country B.",
            size=13, color=MID_GREY))

        self._a_label = make_label("Country A: Not set", size=13, bold=True)
        self._b_label = make_label("Country B: Not set", size=13, bold=True)
        self._content.add_widget(self._a_label)
        self._content.add_widget(self._b_label)

        clear_btn = make_button("🔄 Clear Selection",
                                bg=(0.25, 0.27, 0.32, 1),
                                on_press=lambda *a: self._clear())
        self._content.add_widget(clear_btn)

        self._compare_btn = make_button(
            "⚖️ Compare Now",
            on_press=lambda *a: self._do_compare())
        self._content.add_widget(self._compare_btn)

        self._result_box = BoxLayout(orientation="vertical",
                                      size_hint_y=None, spacing=dp(6))
        self._result_box.bind(minimum_height=self._result_box.setter("height"))
        self._content.add_widget(self._result_box)

        sv.add_widget(self._content)
        root.add_widget(sv)

        bar = nav_bar(None, "compare")
        self._bar = bar
        root.add_widget(bar)
        self._root = root
        self.add_widget(root)

    def on_enter(self):
        self._root.remove_widget(self._bar)
        self._bar = nav_bar(self.manager, "compare")
        self._root.add_widget(self._bar)
        self._refresh_labels()

    def _refresh_labels(self):
        a = AppState.compare_a
        b = AppState.compare_b
        self._a_label.text = f"Country A: [b]{a.name}[/b]" if a else "Country A: Not set"
        self._b_label.text = f"Country B: [b]{b.name}[/b]" if b else "Country B: Not set"

    def _clear(self):
        AppState.compare_a = None
        AppState.compare_b = None
        self._result_box.clear_widgets()
        self._refresh_labels()

    def _do_compare(self):
        a, b = AppState.compare_a, AppState.compare_b
        if not a or not b:
            show_popup("Select Both Countries",
                       "Set both Country A and Country B first.", error=True)
            return
        self._result_box.clear_widgets()
        self._result_box.add_widget(make_label(
            "Building comparison…", size=13, color=MID_GREY, italic=True))

        comp = CountryComparator(None).compare(a, b)
        Clock.schedule_once(lambda *a: self._show_table(comp, a, b))

        guide = AppState.get_guide()
        if guide:
            threading.Thread(
                target=self._ai_compare, args=(guide, a, b), daemon=True).start()

    def _show_table(self, comp, a, b):
        self._result_box.clear_widgets()
        rows = [
            ("Capital", comp["capital_a"], comp["capital_b"]),
            ("Region", comp["region_a"], comp["region_b"]),
            ("Population",
             f"{comp['population_a']:,}", f"{comp['population_b']:,}"),
            ("Area",
             f"{comp['area_a']:,.0f} km²", f"{comp['area_b']:,.0f} km²"),
            ("Languages",
             ", ".join(comp["languages_a"]) or "N/A",
             ", ".join(comp["languages_b"]) or "N/A"),
            ("Currencies",
             ", ".join(comp["currencies_a"]),
             ", ".join(comp["currencies_b"])),
        ]
        header = GridLayout(cols=3, size_hint=(1, None), height=dp(40))
        for txt, bg in [("Field", PAPER),
                         (comp["country_a"], INK),
                         (comp["country_b"], INK)]:
            lbl = Label(text=txt, bold=True, font_size=dp(12),
                        color=INK if bg == PAPER else WHITE)
            with lbl.canvas.before:
                from kivy.graphics import Color, Rectangle
                Color(*bg)
                lbl._bg = Rectangle(pos=lbl.pos, size=lbl.size)
            lbl.bind(pos=lambda w, *a: setattr(w._bg, "pos", w.pos))
            lbl.bind(size=lambda w, *a: setattr(w._bg, "size", w.size))
            header.add_widget(lbl)
        self._result_box.add_widget(header)

        for label, va, vb in rows:
            row = GridLayout(cols=3, size_hint=(1, None), height=dp(44))
            for txt, bg in [(label, LIGHT_GREY), (va, WHITE), (vb, WHITE)]:
                lbl = Label(text=txt, font_size=dp(11),
                            color=MID_GREY if bg == LIGHT_GREY else INK,
                            bold=(bg == LIGHT_GREY))
                with lbl.canvas.before:
                    from kivy.graphics import Color, Rectangle
                    Color(*bg)
                    lbl._bg = Rectangle(pos=lbl.pos, size=lbl.size)
                lbl.bind(pos=lambda w, *a: setattr(w._bg, "pos", w.pos))
                lbl.bind(size=lambda w, *a: setattr(w._bg, "size", w.size))
                row.add_widget(lbl)
            self._result_box.add_widget(row)

        diff = comp.get("tz_difference_hours")
        if diff is not None:
            self._result_box.add_widget(make_label(
                f"🕐 Timezone difference: [b]{diff:.1f} hrs[/b]",
                size=13))

        self._ai_label = make_label(
            "⏳ Generating AI comparison…", size=13, color=MID_GREY, italic=True)
        self._result_box.add_widget(self._ai_label)

    def _ai_compare(self, guide, a, b):
        try:
            comparator = CountryComparator(guide)
            text = comparator.ai_comparison(a, b)
            Clock.schedule_once(lambda *a: self._show_ai(text, a, b))
        except Exception as e:
            Clock.schedule_once(
                lambda *a: self._show_ai(None, error=str(e)))

    def _show_ai(self, text, a=None, b=None, error=None):
        try:
            self._result_box.remove_widget(self._ai_label)
        except Exception:
            pass
        if error:
            self._result_box.add_widget(
                make_label(f"AI error: {error}", size=12, color=DANGER))
            return
        self._ai_text = text
        self._result_box.add_widget(
            make_label("🤖 AI Analysis", size=13, bold=True))
        self._result_box.add_widget(make_label(text, size=12))
        if a and b:
            self._result_box.add_widget(make_button(
                "💾 Save Comparison",
                bg=SUCCESS,
                on_press=lambda *x: self._save(a, b)))

    def _save(self, a, b):
        fname = f"{a.name}_vs_{b.name}_comparison.txt".replace(" ", "_")
        try:
            msg = save_guide(self._ai_text, fname)
            show_popup("Saved", f"{msg}\n→ saved_guides/{fname}")
        except Exception as e:
            show_popup("Error", str(e), error=True)


class SavedScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)

        header = BoxLayout(size_hint=(1, None), height=dp(56),
                           padding=[dp(16), 0])
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*INK)
            header._bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(header._bg, "pos", header.pos))
        header.bind(size=lambda *a: setattr(header._bg, "size", header.size))
        header.add_widget(make_label(
            "📂  Saved Guides", size=17, bold=True, color=WHITE))
        root.add_widget(header)

        refresh_bar = BoxLayout(size_hint=(1, None), height=dp(44),
                                padding=dp(8))
        refresh_bar.add_widget(make_button(
            "🔄 Refresh", height=36,
            bg=(0.25, 0.27, 0.32, 1),
            on_press=lambda *a: self._load()))
        root.add_widget(refresh_bar)

        sv = ScrollView(size_hint=(1, 1))
        self._content = BoxLayout(orientation="vertical",
                                   size_hint_y=None, spacing=dp(8),
                                   padding=dp(14))
        self._content.bind(minimum_height=self._content.setter("height"))
        sv.add_widget(self._content)
        root.add_widget(sv)

        bar = nav_bar(None, "saved")
        self._bar = bar
        root.add_widget(bar)
        self._root = root
        self.add_widget(root)

    def on_enter(self):
        self._root.remove_widget(self._bar)
        self._bar = nav_bar(self.manager, "saved")
        self._root.add_widget(self._bar)
        self._load()

    def _load(self):
        self._content.clear_widgets()
        files = list_saved_guides()
        if not files:
            self._content.add_widget(make_label(
                "No saved guides yet.\nGenerate a guide and tap 💾 Save.",
                size=13, color=MID_GREY, italic=True))
            return
        for fname in files:
            row = BoxLayout(size_hint=(1, None), height=dp(54),
                            spacing=dp(8))
            lbl = make_label(f"📝 {fname}", size=13, wrap=True)
            lbl.size_hint = (1, 1)
            row.add_widget(lbl)
            view_btn = make_button("View", bg=ACCENT,
                                   height=40, on_press=lambda b, f=fname: self._view(f))
            view_btn.size_hint = (None, None)
            view_btn.width = dp(60)
            row.add_widget(view_btn)
            self._content.add_widget(row)

    def _view(self, fname):
        try:
            text = load_saved_guide(fname)
        except Exception as e:
            show_popup("Error", str(e), error=True)
            return

        sv = ScrollView(size_hint=(1, 1))
        inner = BoxLayout(orientation="vertical", size_hint_y=None,
                          padding=dp(14), spacing=dp(8))
        inner.bind(minimum_height=inner.setter("height"))
        inner.add_widget(make_label(text, size=12))
        sv.add_widget(inner)

        close_btn = make_button("Close", bg=MID_GREY)
        content = BoxLayout(orientation="vertical", spacing=dp(8))
        content.add_widget(sv)
        content.add_widget(close_btn)

        popup = Popup(title=fname, content=content,
                      size_hint=(0.95, 0.85),
                      title_color=WHITE, title_size=dp(13))
        close_btn.bind(on_press=popup.dismiss)
        popup.open()


class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)

        header = BoxLayout(size_hint=(1, None), height=dp(56),
                           padding=[dp(16), 0])
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*INK)
            header._bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(header._bg, "pos", header.pos))
        header.bind(size=lambda *a: setattr(header._bg, "size", header.size))
        header.add_widget(make_label(
            "⚙️  Settings", size=17, bold=True, color=WHITE))
        root.add_widget(header)

        sv = ScrollView(size_hint=(1, 1))
        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=dp(16), padding=dp(16))
        content.bind(minimum_height=content.setter("height"))

        content.add_widget(make_label(
            "Gemini API Key", size=13, bold=True))
        content.add_widget(make_label(
            "Required for AI guides, checklists, and comparisons.\n"
            "Get a free key at aistudio.google.com",
            size=12, color=MID_GREY))

        self.key_input = make_input(
            "Paste your Gemini API key here…",
            password=True, height=48)
        if AppState.gemini_key:
            self.key_input.text = AppState.gemini_key
        content.add_widget(self.key_input)

        content.add_widget(make_button(
            "💾 Save Key", bg=SUCCESS,
            on_press=lambda *a: self._save_key()))

        content.add_widget(make_label("─" * 60, size=10, color=LIGHT_GREY))
        content.add_widget(make_label("Models Used", size=13, bold=True))
        content.add_widget(make_label(
            "Primary:  gemini-2.5-flash\n"
            "Fallback: gemini-2.5-flash-lite\n\n"
            "Both are free-tier eligible with billing enabled.",
            size=12, color=MID_GREY))

        content.add_widget(make_label("─" * 60, size=10, color=LIGHT_GREY))
        content.add_widget(make_label("Data Source", size=13, bold=True))
        content.add_widget(make_label(
            "Country data: CountriesNow API (free, no key needed)\n"
            "countriesnow.space",
            size=12, color=MID_GREY))

        sv.add_widget(content)
        root.add_widget(sv)

        bar = nav_bar(None, "settings")
        self._bar = bar
        root.add_widget(bar)
        self._root = root
        self.add_widget(root)

    def on_enter(self):
        self._root.remove_widget(self._bar)
        self._bar = nav_bar(self.manager, "settings")
        self._root.add_widget(self._bar)

    def _save_key(self):
        key = self.key_input.text.strip()
        if not key:
            show_popup("Empty Key", "Please paste your Gemini API key.", error=True)
            return
        AppState.gemini_key = key
        AppState.guide_client = None  # force re-init with new key
        show_popup("Saved ✅", "API key saved. AI features are now active.")


# ── App Entry Point ──────────────────────────

class GlobeGuideApp(App):
    def build(self):
        Window.clearcolor = PAPER

        sm = ScreenManager()
        sm.add_widget(SearchScreen(name="search"))
        sm.add_widget(DetailScreen(name="detail"))
        sm.add_widget(GuideScreen(name="guide"))
        sm.add_widget(ChecklistScreen(name="checklist"))
        sm.add_widget(CompareScreen(name="compare"))
        sm.add_widget(SavedScreen(name="saved"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm

    def get_application_name(self):
        return "Globe Guide"


if __name__ == "__main__":
    GlobeGuideApp().run()
