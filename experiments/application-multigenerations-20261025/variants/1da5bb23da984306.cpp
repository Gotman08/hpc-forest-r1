#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    int root = 0;
    while ((root + 1) * (root + 1) <= limit) ++root;

    const int base_count = root >= 3 ? (root - 1) / 2 : 0;
    std::vector<unsigned char> base_composite(static_cast<std::size_t>(base_count), 0);
    for (int i = 0; i < base_count; ++i) {
        const int p = 3 + 2 * i;
        if (p * p > root) break;
        if (base_composite[static_cast<std::size_t>(i)] == 0) {
            for (int j = (p * p - 3) / 2; j < base_count; j += p) {
                base_composite[static_cast<std::size_t>(j)] = 1;
            }
        }
    }

    std::vector<int> base_primes;
    for (int i = 0; i < base_count; ++i) {
        if (base_composite[static_cast<std::size_t>(i)] == 0) {
            base_primes.push_back(3 + 2 * i);
        }
    }

    std::uint64_t sum = limit >= 2 ? 2 : 0;
    constexpr int kSegmentOdds = 16384;
    for (int low = 3; low <= limit;) {
        const int count = std::min(kSegmentOdds, (limit - low) / 2 + 1);
        const int high = low + 2 * (count - 1);
        std::vector<unsigned char> composite(static_cast<std::size_t>(count), 0);

        for (const int p : base_primes) {
            if (p * p > high) break;
            int first = std::max(p * p, ((low + p - 1) / p) * p);
            if ((first & 1) == 0) first += p;
            for (int multiple = first; multiple <= high; multiple += 2 * p) {
                composite[static_cast<std::size_t>((multiple - low) / 2)] = 1;
            }
        }

        for (int i = 0; i < count; ++i) {
            if (composite[static_cast<std::size_t>(i)] == 0) {
                sum += static_cast<std::uint64_t>(low + 2 * i);
            }
        }
        low = high + 2;
    }

    std::cout << sum << '\n';
}
