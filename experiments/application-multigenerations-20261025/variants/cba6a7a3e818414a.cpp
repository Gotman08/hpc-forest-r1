#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    const int odd_count = limit >= 3 ? (limit - 1) / 2 : 0;
    std::vector<unsigned char> composite(odd_count, 0);
    for (int i = 0; i < odd_count; ++i) {
        const int p = 2 * i + 3;
        if (p > limit / p) break;
        if (composite[i] == 0) {
            for (int j = (p * p - 3) / 2; j < odd_count; j += p) {
                composite[j] = 1;
            }
        }
    }

    std::uint64_t sum = limit >= 2 ? 2 : 0;
    std::uint64_t partial0 = 0;
    std::uint64_t partial1 = 0;
    std::uint64_t partial2 = 0;
    std::uint64_t partial3 = 0;
    int i = 0;
    for (; i + 3 < odd_count; i += 4) {
        partial0 += static_cast<std::uint64_t>(2 * i + 3) * (1u - composite[i]);
        partial1 += static_cast<std::uint64_t>(2 * (i + 1) + 3) * (1u - composite[i + 1]);
        partial2 += static_cast<std::uint64_t>(2 * (i + 2) + 3) * (1u - composite[i + 2]);
        partial3 += static_cast<std::uint64_t>(2 * (i + 3) + 3) * (1u - composite[i + 3]);
    }
    sum += partial0 + partial1 + partial2 + partial3;
    for (; i < odd_count; ++i) {
        sum += static_cast<std::uint64_t>(2 * i + 3) * (1u - composite[i]);
    }

    std::cout << sum << '\n';
}
