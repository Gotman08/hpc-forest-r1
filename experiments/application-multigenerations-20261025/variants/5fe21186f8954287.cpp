#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

namespace {
constexpr std::size_t kSegmentOdds = 4096;

std::vector<int> primes_up_to(int limit) {
    int root = 1;
    while (root + 1 <= limit / (root + 1)) ++root;

    const std::size_t odd_count =
        root >= 3 ? static_cast<std::size_t>((root - 1) / 2) : 0;
    std::vector<unsigned char> composite(odd_count, 0);
    for (std::size_t i = 0; i < odd_count; ++i) {
        const int p = static_cast<int>(3 + 2 * i);
        if (p > root / p) break;
        if (composite[i]) continue;
        for (std::size_t j = static_cast<std::size_t>((p * p - 3) / 2);
             j < odd_count; j += static_cast<std::size_t>(p)) {
            composite[j] = 1;
        }
    }

    std::vector<int> primes;
    for (std::size_t i = 0; i < odd_count; ++i) {
        if (!composite[i]) primes.push_back(static_cast<int>(3 + 2 * i));
    }
    return primes;
}
}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    std::uint64_t sum = limit >= 2 ? 2 : 0;
    if (limit >= 3) {
        const std::vector<int> base_primes = primes_up_to(limit);
        const std::size_t odd_count =
            static_cast<std::size_t>((limit - 1) / 2);
        std::vector<unsigned char> composite(
            std::min(odd_count, kSegmentOdds), 0);

        for (std::size_t segment_start = 0; segment_start < odd_count;
             segment_start += kSegmentOdds) {
            const std::size_t count =
                std::min(kSegmentOdds, odd_count - segment_start);
            std::fill(composite.begin(), composite.begin() + count, 0);

            const int low = static_cast<int>(3 + 2 * segment_start);
            const int high = static_cast<int>(low + 2 * (count - 1));
            for (const int p : base_primes) {
                if (p > high / p) break;

                int first = p * p;
                if (first < low) {
                    const int remainder = low % p;
                    first = remainder == 0 ? low : low + (p - remainder);
                }
                if ((first & 1) == 0) first += p;
                if (first > high) continue;

                for (std::size_t i =
                         static_cast<std::size_t>((first - low) / 2);
                     i < count; i += static_cast<std::size_t>(p)) {
                    composite[i] = 1;
                }
            }

            for (std::size_t i = 0; i < count; ++i) {
                if (!composite[i]) {
                    sum += static_cast<std::uint64_t>(low + 2 * i);
                }
            }
        }
    }

    std::cout << sum << '\n';
}
