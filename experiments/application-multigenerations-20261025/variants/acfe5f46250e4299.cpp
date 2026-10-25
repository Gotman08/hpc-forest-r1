#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    const std::size_t odd_count = limit >= 3
        ? static_cast<std::size_t>((limit - 1) / 2)
        : 0;
    std::vector<unsigned char> composite(odd_count, 0);

    const std::uint64_t count = static_cast<std::uint64_t>(odd_count);
    std::uint64_t sum = limit >= 2 ? 2 : 0;
    sum += count * (count + 2);

    for (std::size_t i = 0; i < odd_count; ++i) {
        const std::uint64_t p = 3 + 2 * static_cast<std::uint64_t>(i);
        if (p > static_cast<std::uint64_t>(limit) / p) break;
        if (composite[i]) continue;

        const std::size_t first = static_cast<std::size_t>((p * p - 3) / 2);
        const std::size_t stride = static_cast<std::size_t>(p);
        for (std::size_t j = first; j < odd_count; j += stride) {
            if (!composite[j]) {
                sum -= 3 + 2 * static_cast<std::uint64_t>(j);
                composite[j] = 1;
            }
        }
    }

    std::cout << sum << '\n';
}
