#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    std::uint64_t sum = 0;
    std::vector<int> primes;
    primes.reserve(static_cast<std::size_t>(limit / 8 + 3));
    if (limit >= 2) { primes.push_back(2); sum += 2; }
    if (limit >= 3) { primes.push_back(3); sum += 3; }
    if (limit >= 5) { primes.push_back(5); sum += 5; }

    const int gaps[] = {4, 2, 4, 2, 4, 6, 2, 6};
    int candidate = 7;
    int gap_index = 0;
    while (candidate <= limit) {
        bool prime = true;
        for (int divisor : primes) {
            if (divisor > candidate / divisor) break;
            if (candidate % divisor == 0) {
                prime = false;
                break;
            }
        }
        if (prime) {
            primes.push_back(candidate);
            sum += static_cast<std::uint64_t>(candidate);
        }
        candidate += gaps[gap_index];
        gap_index = (gap_index + 1) & 7;
    }

    std::cout << sum << '\n';
}
