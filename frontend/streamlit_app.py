"""
Streamlit frontend for the C++ to Python translation app.

Run locally with:
    streamlit run frontend/streamlit_app.py
"""

import os

import requests
import streamlit as st

try:
    from backend.cpp_python_translator import translate_competitive_cpp
except ImportError:
    translate_competitive_cpp = None


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000/translate"
BACKEND_URL = os.getenv("TRANSLATE_API_URL", DEFAULT_BACKEND_URL)
REQUEST_TIMEOUT_SECONDS = 120


st.set_page_config(
    page_title="C++ to Python Translator",
    page_icon="</>",
    layout="wide",
)


st.title("C++ to Python Translator")
st.caption("Translate competitive-programming C++ solutions into Python.")


default_cpp_code = """#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    vector<int> a(n);
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }

    long long sum = 0;
    for (int x : a) {
        sum += x;
    }

    cout << sum << '\\n';
    return 0;
}
"""


source_code = st.text_area(
    label="C++ source code",
    value=default_cpp_code,
    height=420,
)


translate_clicked = st.button(
    "Translate",
    type="primary",
    use_container_width=False,
)


def render_translated_code(translated_code: str) -> None:
    if not translated_code:
        st.error("No translated code was produced.")
        return

    st.subheader("Translated Python")
    st.code(translated_code, language="python")


def translate_locally(source_code_to_translate: str) -> str | None:
    if translate_competitive_cpp is None:
        return None
    return translate_competitive_cpp(source_code_to_translate)


if translate_clicked:
    cleaned_source_code = source_code.strip()

    if not cleaned_source_code:
        st.warning("Please enter C++ code before translating.")
    else:
        # HTTP request handling:
        # - The frontend sends JSON because the FastAPI endpoint expects a
        #   Pydantic body with the source_code string field.
        # - requests.post serializes the dict below to:
        #     {"source_code": "..."}
        # - timeout prevents the UI from hanging forever if the model server is
        #   cold, overloaded, or unreachable.
        payload = {"source_code": cleaned_source_code}

        with st.spinner("Translating..."):
            try:
                response = requests.post(
                    BACKEND_URL,
                    json=payload,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

                # Raise an exception for 4xx/5xx responses so they are handled
                # in one place below instead of silently rendering bad output.
                response.raise_for_status()

                # FastAPI returns JSON shaped like:
                #     {"translated_code": "print(...)"}
                response_json = response.json()
                translated_code = response_json.get("translated_code", "")

                render_translated_code(translated_code)

            except requests.exceptions.ConnectionError:
                translated_code = translate_locally(cleaned_source_code)
                if translated_code is None:
                    st.error(
                        "Could not reach the FastAPI backend and local translation "
                        "is unavailable in this build."
                    )
                else:
                    st.warning("FastAPI was unavailable, so local translation was used.")
                    render_translated_code(translated_code)
            except requests.exceptions.Timeout:
                translated_code = translate_locally(cleaned_source_code)
                if translated_code is None:
                    st.error(
                        "The translation request timed out and local translation "
                        "is unavailable in this build."
                    )
                else:
                    st.warning("The backend timed out, so local translation was used.")
                    render_translated_code(translated_code)
            except requests.exceptions.HTTPError as exc:
                error_message = response.text if "response" in locals() else str(exc)
                st.error(f"The backend returned an error: {error_message}")
            except ValueError:
                st.error("The backend response was not valid JSON.")
            except requests.exceptions.RequestException as exc:
                translated_code = translate_locally(cleaned_source_code)
                if translated_code is None:
                    st.error(f"Request failed: {exc}")
                else:
                    st.warning("The backend request failed, so local translation was used.")
                    render_translated_code(translated_code)
