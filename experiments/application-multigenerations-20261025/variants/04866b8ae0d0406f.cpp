#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    std::uint64_t sum = 0;
    // At most floor(sqrt(200000)) distinct primes can be needed as divisors.
    std::array<int, 448> primes{};
    std::size_t prime_count = 0;

    if (limit >= 2) {
        sum += 2;
        if (2 <= limit / 2) primes[prime_count++] = 2;
    }
    if (limit >= 3) {
        sum += 3;
        if (3 <= limit / 3) primes[prime_count++] = 3;
    }
    if (limit >= 5) {
        sum += 5;
        if (5 <= limit / 5) primes[prime_count++] = 5;
    }

    const int gaps[] = {4, 2, 4, 2, 4, 6, 2, 6};
    int candidate = 7;
    int gap_index = 0;
    while (candidate <= limit) {
        bool prime = true;
        for (std::size_t i = 0; i < prime_count; ++i) {
            const int divisor = primes[i];
            if (divisor > candidate / divisor) break;
            if (candidate % divisor == 0) {
                prime = false;
                break;
            }
        }
        if (prime) {
            sum += static_cast<std::uint64_t>(candidate);
            if (candidate <= limit / candidate) {
                primes[prime_count++] = candidate;
            }
        }
        candidate += gaps[gap_index];
        gap_index = (gap_index + 1) & 7;
    }

    std::cout << sum << '\n';
}
