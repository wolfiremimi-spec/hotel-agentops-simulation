"""Minimal stand-in for Streamlit so a page script can be exercised against the real engine.

It records what the page renders, returns scripted widget values by key, and emulates
st.stop / st.rerun by raising, so a test can drive reruns just like a browser would.
"""
import runpy
import sys
import types


class Stop(Exception):
    pass


class Rerun(Exception):
    pass


class SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as exc:
            raise AttributeError(k) from exc

    def __setattr__(self, k, v):
        self[k] = v

    def __delattr__(self, k):
        del self[k]


class Harness:
    def __init__(self):
        self.session_state = SessionState()
        self.clicks = set()
        self.values = {}
        self.out = []
        self.keys_seen = []

    # ---- recording helpers ----
    def _rec(self, kind, *a):
        self.out.append((kind,) + tuple(str(x) for x in a))

    def _key(self, key):
        if key is not None:
            if key in self.keys_seen:
                raise AssertionError(f"duplicate widget key {key}")
            self.keys_seen.append(key)


H = Harness()


class Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return getattr(st_mod, name)


def _noop_factory(kind):
    def f(*a, **k):
        H._rec(kind, *a[:1])
    return f


def button(label, *a, key=None, **k):
    H._key(key)
    H._rec("button", label)
    return (key or label) in H.clicks


def download_button(label, data, *a, key=None, **k):
    H._key(key)
    assert isinstance(data, (bytes, str)) and len(data) > 0, f"empty download {label}"
    H._rec("download", label, len(data))
    return False


def radio(label, options, index=0, key=None, **k):
    H._key(key)
    allowed = {"horizontal", "help", "on_change", "args", "kwargs", "disabled", "label_visibility", "captions", "format_func"}
    bad = set(k) - allowed
    assert not bad, f"st.radio got unsupported args {bad}"
    if key in H.values:
        v = H.values[key]
        assert v in options, f"{v} not in {options}"
    else:
        v = None if index is None else options[index]
    H.session_state[key] = v
    return v


def selectbox(label, options, index=0, key=None, **k):
    H._key(key)
    options = list(options)
    v = H.values[key] if key in H.values else (options[index] if options else None)
    H.session_state[key] = v
    return v


def number_input(label, min_value=None, max_value=None, value=None, step=None, key=None, **k):
    H._key(key)
    H.session_state[key] = H.values.get(key, value)
    return H.session_state[key]


def text_input(label, value="", key=None, **k):
    H._key(key)
    H.session_state[key] = H.values.get(key, value)
    return H.session_state[key]


def columns(spec, **k):
    n = spec if isinstance(spec, int) else len(spec)
    return [Ctx() for _ in range(n)]


def container(**k):
    return Ctx()


def expander(label, **k):
    H._rec('expander', label)
    return Ctx()


def stop():
    raise Stop()


def rerun():
    raise Rerun()


st_mod = types.ModuleType("streamlit")
for name in ["markdown", "write", "info", "caption", "success", "error", "warning", "dataframe", "metric", "plotly_chart", "page_link", "video", "link_button"]:
    setattr(st_mod, name, _noop_factory(name))
st_mod.button = button
st_mod.download_button = download_button
st_mod.radio = radio
st_mod.selectbox = selectbox
st_mod.number_input = number_input
st_mod.text_input = text_input
st_mod.columns = columns
st_mod.container = container
st_mod.expander = expander
st_mod.stop = stop
st_mod.rerun = rerun
st_mod.session_state = H.session_state

# plotly stand-in: only what the page and ui.py touch
go_mod = types.ModuleType("plotly.graph_objects")


class _Fig:
    def __init__(self, *a, **k):
        self.traces = []

    def add_bar(self, **k):
        assert len(k["x"]) == len(k["y"]) and k["x"], "bar with no data"
        self.traces.append(k)

    def update_layout(self, **k):
        pass

    def add_hline(self, **k):
        pass

    def add_scatter(self, **k):
        assert len(k["x"]) == len(k["y"]) and k["x"], "scatter with no data"
        self.traces.append(k)


go_mod.Figure = _Fig
go_mod.Bar = lambda *a, **k: None
go_mod.Heatmap = lambda *a, **k: None
go_mod.Waterfall = lambda *a, **k: None
go_mod.Scatter = lambda *a, **k: None
go_mod.layout = types.SimpleNamespace(Template=lambda **k: None)
go_mod.Layout = lambda **k: None
pio_mod = types.ModuleType("plotly.io")
class _T(dict):
    default = None


pio_mod.templates = _T()
plotly_mod = types.ModuleType("plotly")
plotly_mod.graph_objects = go_mod
plotly_mod.io = pio_mod
sys.modules.update({"streamlit": st_mod, "plotly": plotly_mod, "plotly.graph_objects": go_mod, "plotly.io": pio_mod})


def run_page(path, max_reruns=5):
    """Run the page once, following st.rerun like Streamlit does. Returns 'stop' or 'end'."""
    for _ in range(max_reruns):
        H.out.clear()
        H.keys_seen.clear()
        try:
            runpy.run_path(path, run_name="__main__")
            result = "end"
        except Stop:
            result = "stop"
        except Rerun:
            H.clicks.clear()
            continue
        H.clicks.clear()
        return result
    raise AssertionError("rerun loop")


def rendered(kind=None):
    return [o for o in H.out if kind is None or o[0] == kind]


def text():
    return "\n".join(" | ".join(o) for o in H.out)


# ---- additions for Scenario Lab: forms, tabs, sliders, callbacks ----
H.pending = []
H.switched = None


def _widget_value(key, default):
    if key in H.values:
        return H.values[key]
    if key in H.session_state:
        return H.session_state[key]
    return default


def button(label, *a, key=None, on_click=None, args=(), kwargs=None, **k):  # noqa: F811
    H._key(key)
    H._rec("button", label, k.get("type", "secondary"))
    hit = (key or label) in H.clicks
    if hit and on_click:
        H.pending.append((on_click, args, kwargs or {}))
    return hit


def form_submit_button(label, *a, key=None, on_click=None, args=(), kwargs=None, **k):
    H._rec("button", label)
    hit = "FORM_SUBMIT" in H.clicks or label in H.clicks
    if hit and on_click:
        H.pending.append((on_click, args, kwargs or {}))
    return hit


def slider(label, min_value=None, max_value=None, value=None, step=None, key=None, **k):
    H._key(key)
    v = _widget_value(key, value if value is not None else min_value)
    assert min_value <= v <= max_value, f"{key}={v} outside [{min_value},{max_value}]"
    H.session_state[key] = v
    return v


def selectbox(label, options, index=0, key=None, **k):  # noqa: F811
    H._key(key)
    options = list(options)
    v = _widget_value(key, options[index] if options and index is not None else None)
    assert v in options, f"{key}={v} not in options"
    H.session_state[key] = v
    return v


def tabs(labels):
    return [Ctx() for _ in labels]


def form(key, **k):
    return Ctx()


def switch_page(p):
    H.switched = p
    raise Stop()


for _n, _f in dict(button=button, form_submit_button=form_submit_button, slider=slider, selectbox=selectbox,
                   tabs=tabs, form=form, switch_page=switch_page).items():
    setattr(st_mod, _n, _f)


def run_page(path, max_reruns=5):  # noqa: F811
    """Like Streamlit: a click runs its callback, then the script reruns."""
    for _ in range(max_reruns):
        H.out.clear()
        H.keys_seen.clear()
        H.pending.clear()
        try:
            runpy.run_path(path, run_name="__main__")
            result = "end"
        except Stop:
            result = "stop"
        except Rerun:
            H.clicks.clear()
            continue
        if H.pending:
            for fn, a, kw in list(H.pending):
                fn(*a, **kw)
            H.clicks.clear()
            H.values.clear()
            continue
        H.clicks.clear()
        return result
    raise AssertionError("rerun loop")


# ---- additions for the copilot app ----
class _Secrets(dict):
    pass


st_mod.secrets = _Secrets()
st_mod.set_page_config = lambda **k: None
st_mod.divider = lambda: H._rec("divider")
st_mod.code = lambda body, **k: H._rec("code", body)
st_mod.sidebar = Ctx()
st_mod.chat_message = lambda role, **k: (H._rec("chat_message", role), Ctx())[1]
st_mod.spinner = lambda *a, **k: Ctx()
H.chat_input_value = None


def chat_input(placeholder="", key=None, disabled=False, **k):
    H._rec("chat_input", placeholder, disabled)
    v, H.chat_input_value = H.chat_input_value, None
    return v


st_mod.chat_input = chat_input

st_mod.expander = expander


# ---- additions for the product app ----
import datetime as _dt
H.nav_target = None


class _Page:
    def __init__(self, path, title="", icon=None, default=False, **k):
        self.path, self.title, self.default = path, title, default


class _Nav:
    def __init__(self, pages):
        flat = [p for group in (pages.values() if isinstance(pages, dict) else [pages]) for p in group]
        self.pages = flat

    def run(self):
        target = H.nav_target
        page = next((p for p in self.pages if p.path == target), None) or next(p for p in self.pages if p.default)
        H.current_page = page.path
        runpy.run_path(page.path, run_name="__page__")


def navigation(pages, **k):
    H.nav_pages = pages
    return _Nav(pages)


def switch_page(p):  # noqa: F811
    H.nav_target = p
    raise Rerun()


class _ColCfg:
    def __getattr__(self, n):
        return lambda *a, **k: {"type": n, **k}


def data_editor(df, key=None, **k):
    H._key(key)
    H._rec("data_editor", key, len(df))
    v = H.values.get(key)
    return v if v is not None else df


def date_input(label, value=None, key=None, **k):
    H._key(key)
    v = _widget_value(key, value)
    H.session_state[key] = v
    return v


def text_area(label, value="", key=None, **k):
    H._key(key)
    v = _widget_value(key, value)
    H.session_state[key] = v
    return v


def file_uploader(label, key=None, **k):
    H._key(key)
    return H.values.get(key)


def multiselect(label, options, default=None, key=None, **k):
    H._key(key)
    v = _widget_value(key, default or [])
    H.session_state[key] = v
    return v


def number_input(label, min_value=None, max_value=None, value="__min__", step=None, key=None, **k):  # noqa: F811
    H._key(key)
    if key in H.values:
        v = H.values[key]
    elif key in H.session_state:
        v = H.session_state[key]
    else:
        v = min_value if value == "__min__" else value
    if v is not None:
        assert (min_value is None or v >= min_value) and (max_value is None or v <= max_value), f"{key}={v} outside range"
    H.session_state[key] = v
    return v


def text_input(label, value="", key=None, **k):  # noqa: F811
    H._key(key)
    v = _widget_value(key, value)
    H.session_state[key] = v
    return v


def checkbox(label, value=False, key=None, **k):
    H._key(key)
    v = _widget_value(key, value)
    H.session_state[key] = v
    return v


def radio(label, options, index=0, key=None, **k):  # noqa: F811
    H._key(key)
    v = H.values[key] if key in H.values else (None if index is None else options[index])
    H.session_state[key] = v
    return v


for _n, _f in dict(navigation=navigation, Page=_Page, switch_page=switch_page, data_editor=data_editor, date_input=date_input,
                   text_area=text_area, file_uploader=file_uploader, multiselect=multiselect, number_input=number_input,
                   text_input=text_input, checkbox=checkbox, radio=radio).items():
    setattr(st_mod, _n, _f)
st_mod.column_config = _ColCfg()


def pills(label, options, selection_mode="single", default=None, key=None, **k):
    H._key(key)
    v = H.values[key] if key in H.values else (default if default is not None else ([] if selection_mode == "multi" else None))
    H.session_state[key] = v
    return v


st_mod.pills = pills
st_mod.progress = lambda value, text=None, **k: H._rec("progress", text)
st_mod.success = lambda body, **k: H._rec("success", body)
st_mod.cache_data = lambda f=None, **k: f if f else (lambda g: g)


def run_app(path, max_reruns=8):
    for _ in range(max_reruns):
        H.out.clear(); H.keys_seen.clear(); H.pending.clear()
        try:
            runpy.run_path(path, run_name="__main__")
            result = "end"
        except Stop:
            result = "stop"
        except Rerun:
            H.clicks.clear()
            continue
        if H.pending:
            for fn, a, kw in list(H.pending):
                fn(*a, **kw)
            H.clicks.clear(); H.values.clear()
            continue
        H.clicks.clear()
        return result
    raise AssertionError("rerun loop")


def _metric(label, value=None, delta=None, **k):
    H._rec("metric", label, value, delta)


def _dataframe(data, **k):
    try:
        H._rec("dataframe", data.to_csv(index=False))
    except AttributeError:
        H._rec("dataframe", data)


st_mod.metric = _metric
st_mod.dataframe = _dataframe


def _navigation(pages, position="sidebar", **k):
    H.nav_pages = pages
    return _Nav(pages)


st_mod.navigation = _navigation
