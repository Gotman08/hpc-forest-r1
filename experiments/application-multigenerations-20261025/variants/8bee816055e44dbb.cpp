#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    // Index i represents the odd number 2*i + 3.
    const std::size_t odd_count = limit >= 3
                                      ? static_cast<std::size_t>((limit - 1) / 2)
                                      : 0;
    std::vector<unsigned char> composite(odd_count, 0);

    for (std::size_t index = 0; index < odd_count; ++index) {
        const int p = static_cast<int>(2 * index + 3);
        if (p > limit / p) break;
        if (composite[index]) continue;

        const std::size_t first =
            (static_cast<std::size_t>(p) * static_cast<std::size_t>(p) - 3) / 2;
        for (std::size_t mark = first; mark < odd_count;
             mark += static_cast<std::size_t>(p)) {
            composite[mark] = 1;
        }
    }

    std::uint64_t sum = limit >= 2 ? 2 : 0;
    for (std::size_t index = 0; index < odd_count; ++index) {
        if (!composite[index]) {
            sum += static_cast<std::uint64_t>(2 * index + 3);
        }
    }

    std::cout << sum << '\n';
}
