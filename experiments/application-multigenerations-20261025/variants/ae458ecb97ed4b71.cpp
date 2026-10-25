#include <algorithm>
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

    int root = 0;
    while (root + 1 <= limit / (root + 1)) ++root;
    const int base_odd_count = root >= 3 ? (root - 1) / 2 : 0;
    std::vector<unsigned char> base_composite(
        static_cast<std::size_t>(base_odd_count), 0);
    std::vector<int> base_primes;
    for (int i = 0; i < base_odd_count; ++i) {
        if (base_composite[static_cast<std::size_t>(i)]) continue;
        const int prime = 2 * i + 3;
        base_primes.push_back(prime);
        if (prime <= root / prime) {
            for (int j = (prime * prime - 3) / 2; j < base_odd_count; j += prime) {
                base_composite[static_cast<std::size_t>(j)] = 1;
            }
        }
    }

    constexpr std::size_t kSegmentOdds = 16384;
    for (std::size_t segment_begin = 0;
         segment_begin < static_cast<std::size_t>(odd_count);
         segment_begin += kSegmentOdds) {
        const std::size_t segment_count = std::min(
            kSegmentOdds,
            static_cast<std::size_t>(odd_count) - segment_begin);
        const int segment_low = 2 * static_cast<int>(segment_begin) + 3;
        const int segment_end = segment_low + 2 * static_cast<int>(segment_count);
        std::vector<unsigned char> composite(segment_count, 0);

        for (const int prime : base_primes) {
            if (prime > limit / prime) break;
            int first = segment_low;
            const int remainder = first % prime;
            if (remainder != 0) first += prime - remainder;
            const int square = prime * prime;
            if (first < square) first = square;
            if ((first & 1) == 0) first += prime;
            if (first >= segment_end) continue;

            const int first_index = (first - segment_low) / 2;
            for (int j = first_index; j < static_cast<int>(segment_count); j += prime) {
                composite[static_cast<std::size_t>(j)] = 1;
            }
        }

        for (std::size_t i = 0; i < segment_count; ++i) {
            if (!composite[i]) {
                sum += static_cast<std::uint64_t>(
                    segment_low + 2 * static_cast<int>(i));
            }
        }
    }

    std::cout << sum << '\n';
}
