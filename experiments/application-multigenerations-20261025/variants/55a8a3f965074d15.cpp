#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    const int odd_count = limit >= 3 ? (limit - 1) / 2 : 0;
    std::vector<std::uint64_t> composite((odd_count + 63) / 64, 0);

    for (int p = 3; p <= limit / p; p += 2) {
        const int p_index = (p - 3) / 2;
        const std::uint64_t p_mask = std::uint64_t{1} << (p_index & 63);
        if ((composite[p_index >> 6] & p_mask) != 0) continue;

        for (int n = p * p; n <= limit; n += 2 * p) {
            const int index = (n - 3) / 2;
            composite[index >> 6] |= std::uint64_t{1} << (index & 63);
        }
    }

    std::uint64_t sum = limit >= 2 ? 2 : 0;
    for (int index = 0; index < odd_count; ++index) {
        const std::uint64_t mask = std::uint64_t{1} << (index & 63);
        if ((composite[index >> 6] & mask) == 0) {
            sum += static_cast<std::uint64_t>(2 * index + 3);
        }
    }
    std::cout << sum << '\n';
}
