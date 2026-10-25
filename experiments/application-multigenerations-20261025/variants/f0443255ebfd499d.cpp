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

    for (int p = 3; p * p <= limit; p += 2) {
        const std::size_t p_index = static_cast<std::size_t>((p - 3) / 2);
        if (composite[p_index]) continue;

        const std::size_t step = static_cast<std::size_t>(p);
        std::size_t index = static_cast<std::size_t>((p * p - 3) / 2);
        for (; index + 3 * step < odd_count; index += 4 * step) {
            composite[index] = 1;
            composite[index + step] = 1;
            composite[index + 2 * step] = 1;
            composite[index + 3 * step] = 1;
        }
        for (; index < odd_count; index += step) {
            composite[index] = 1;
        }
    }

    std::uint64_t sum = limit >= 2 ? 2 : 0;
    for (std::size_t i = 0; i < odd_count; ++i) {
        if (!composite[i]) sum += 2 * i + 3;
    }
    std::cout << sum << '\n';
}
