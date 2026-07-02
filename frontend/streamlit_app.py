"""
Streamlit frontend for the C++ to Python translation app.

Run locally with:
    streamlit run frontend/streamlit_app.py
"""

import os

import requests
import streamlit as st


DEFAULT_BACKEND_URL = "http://localhost:8000/translate"
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

        with st.spinner("Translating with CodeT5..."):
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

                if not translated_code:
                    st.error("The backend responded successfully but returned no code.")
                else:
                    st.subheader("Translated Python")
                    st.code(translated_code, language="python")

            except requests.exceptions.ConnectionError:
                st.error(
                    "Could not reach the FastAPI backend. "
                    f"Start it with `uvicorn backend.fastapi_app:app --reload` "
                    f"and confirm it is listening at {BACKEND_URL}."
                )
            except requests.exceptions.Timeout:
                st.error(
                    "The translation request timed out. "
                    "The model may still be loading or the input may be too large."
                )
            except requests.exceptions.HTTPError as exc:
                error_message = response.text if "response" in locals() else str(exc)
                st.error(f"The backend returned an error: {error_message}")
            except ValueError:
                st.error("The backend response was not valid JSON.")
            except requests.exceptions.RequestException as exc:
                st.error(f"Request failed: {exc}")
