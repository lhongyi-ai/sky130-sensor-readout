// Minimal reproducer of the installed ngspice-47 Verilator shim mask.
// The old expression has undefined behavior for i == 32: observed output is
// platform/compiler-specific, not a portable prediction of undefined behavior.
#include <cstdint>
#include <cstdio>

int main() {
    unsigned legacy_errors = 0, fixed_errors = 0;
    for (unsigned hot = 0; hot < 33; ++hot) {
        volatile uint64_t word = uint64_t(1) << hot;
        for (volatile int i = 0; i < 33; ++i) {
            const bool expected = unsigned(i) == hot;
            const bool legacy = (word & (1 << i)) != 0;
            const bool corrected = (word & (uint64_t(1) << i)) != 0;
            legacy_errors += legacy != expected;
            fixed_errors += corrected != expected;
            if (legacy != expected)
                std::printf("legacy_error hot=%u observed_bit=%d value=%d expected=%d\n",
                            hot, int(i), legacy, expected);
        }
    }
    std::printf("legacy_errors=%u fixed_errors=%u checked=1089\n", legacy_errors, fixed_errors);
    return fixed_errors != 0;
}
