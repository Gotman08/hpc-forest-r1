#include <cstdint>
#include <cstdlib>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    std::uint64_t sum = 0;
    if (limit >= 2) sum += 2;
    if (limit >= 3) sum += 3;
    if (limit >= 5) sum += 5;

    if (limit >= 7) {
        std::uint16_t divisor_primes[448] = {2, 3, 5};
        int divisor_count = 3;
        static const int wheel_gaps[8] = {4, 2, 4, 2, 4, 6, 2, 6};
        int gap_index = 0;

        for (int candidate = 7; candidate <= limit;) {
            bool prime = true;
            for (int i = 3; i < divisor_count; ++i) {
                const int divisor = divisor_primes[i];
                if (divisor * divisor > candidate) break;
                if (candidate % divisor == 0) {
                    prime = false;
                    break;
                }
            }

            if (prime) {
                sum += static_cast<std::uint64_t>(candidate);
                if (candidate <= limit / candidate) {
                    divisor_primes[divisor_count++] =
                        static_cast<std::uint16_t>(candidate);
                }
            }

            candidate += wheel_gaps[gap_index];
            gap_index = (gap_index + 1) & 7;
        }
    }

    std::cout << sum << '\n';
}
