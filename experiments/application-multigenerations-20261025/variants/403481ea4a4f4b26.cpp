#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    int root_limit = 0;
    while (root_limit + 1 <= limit / (root_limit + 1)) ++root_limit;

    std::uint64_t sum = 0;
    std::vector<std::uint16_t> primes;
    const int initial_primes[] = {2, 3, 5};
    for (int prime : initial_primes) {
        if (prime <= limit) {
            sum += static_cast<std::uint64_t>(prime);
            if (prime <= root_limit) primes.push_back(static_cast<std::uint16_t>(prime));
        }
    }

    const int wheel_gaps[] = {4, 2, 4, 2, 4, 6, 2, 6};
    int candidate = 7;
    int gap_index = 0;
    while (candidate <= limit) {
        bool prime = true;
        for (std::uint16_t divisor : primes) {
            if (divisor > candidate / divisor) break;
            if (candidate % divisor == 0) {
                prime = false;
                break;
            }
        }
        if (prime) {
            sum += static_cast<std::uint64_t>(candidate);
            if (candidate <= root_limit) primes.push_back(static_cast<std::uint16_t>(candidate));
        }
        candidate += wheel_gaps[gap_index];
        gap_index = (gap_index + 1) & 7;
    }

    std::cout << sum << '\n';
}
