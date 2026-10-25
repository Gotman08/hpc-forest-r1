#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    // Store candidates 6k +/- 1, including 1 as a marked non-prime.
    std::size_t candidate_count = 0;
    if (limit >= 1) {
        candidate_count = static_cast<std::size_t>((limit - 1) / 6 + 1);
    }
    if (limit >= 5) {
        candidate_count += static_cast<std::size_t>((limit - 5) / 6 + 1);
    }

    std::vector<std::uint8_t> composite(candidate_count, 0);
    if (candidate_count != 0) composite[0] = 1;

    for (std::size_t i = 1; i < candidate_count; ++i) {
        const std::uint64_t p = 6ULL * static_cast<std::uint64_t>(i / 2) +
                                ((i & 1U) != 0U ? 5ULL : 1ULL);
        const std::uint64_t bound = static_cast<std::uint64_t>(limit);
        if (p > bound / p) break;
        if (composite[i]) continue;

        // Quotients visit only 6k +/- 1, beginning at p, so marking starts at p*p.
        for (std::uint64_t q = p; q <= bound / p;) {
            const std::uint64_t multiple = p * q;
            const std::size_t index = static_cast<std::size_t>(
                2ULL * (multiple / 6) + (multiple % 6 == 5));
            composite[index] = 1;
            q += (q % 6 == 1) ? 4 : 2;
        }
    }

    std::uint64_t sum = 0;
    if (limit >= 2) sum += 2;
    if (limit >= 3) sum += 3;
    for (std::size_t i = 1; i < candidate_count; ++i) {
        if (!composite[i]) {
            sum += 6ULL * static_cast<std::uint64_t>(i / 2) +
                   ((i & 1U) != 0U ? 5ULL : 1ULL);
        }
    }

    std::cout << sum << '\n';
}
