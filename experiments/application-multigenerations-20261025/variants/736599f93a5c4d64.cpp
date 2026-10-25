#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    std::uint64_t sum = limit >= 2 ? 2 : 0;
    const int odd_count = limit >= 3 ? (limit - 1) / 2 : 0;
    std::vector<unsigned char> composite(static_cast<std::size_t>(odd_count), 0);

    for (int i = 0; i < odd_count; ++i) {
        if (composite[static_cast<std::size_t>(i)]) continue;
        const int prime = 2 * i + 3;
        if (prime <= limit / prime) {
            for (int j = (prime * prime - 3) / 2; j < odd_count; j += prime) {
                composite[static_cast<std::size_t>(j)] = 1;
            }
        }
    }

    for (int i = 0; i < odd_count; ++i) {
        if (!composite[static_cast<std::size_t>(i)]) sum += 2 * i + 3;
    }
    std::cout << sum << '\n';
}
