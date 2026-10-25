#include <cstdint>
#include <cstdlib>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;
    std::uint64_t sum = 0;
    for (int n = 2; n <= limit; ++n) {
        bool prime = true;
        for (int divisor = 2; divisor < n; ++divisor) {
            if (n % divisor == 0) { prime = false; break; }
        }
        if (prime) sum += n;
    }
    std::cout << sum << '\n';
}
