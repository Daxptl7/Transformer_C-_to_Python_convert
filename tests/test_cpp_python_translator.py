import subprocess
import sys
import textwrap

from backend.cpp_python_translator import translate_competitive_cpp


def test_translates_sum_vector_program_to_runnable_python():
    cpp_source = textwrap.dedent(
        r"""
        #include <bits/stdc++.h>
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

            cout << sum << '\n';
            return 0;
        }
        """
    )

    translated = translate_competitive_cpp(cpp_source)

    assert "for i in range(n):" in translated
    assert "print(sum)" in translated

    completed = subprocess.run(
        [sys.executable, "-c", translated],
        input="5\n1 2 3 4 5\n",
        text=True,
        capture_output=True,
        check=True,
    )

    assert completed.stdout.strip() == "15"


def test_splits_single_line_blocks():
    translated = translate_competitive_cpp(
        r"int main(){int n; cin >> n; cout << n << '\n'; return 0;}"
    )

    completed = subprocess.run(
        [sys.executable, "-c", translated],
        input="42\n",
        text=True,
        capture_output=True,
        check=True,
    )

    assert completed.stdout.strip() == "42"
