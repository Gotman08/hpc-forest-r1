#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    std::uint64_t sum = 0;
    if (limit >= 2) sum += 2;
    if (limit >= 3) sum += 3;
    if (limit >= 5) sum += 5;

    // Only primes that can divide a candidate through limit need storing.
    std::vector<int> divisor_primes;
    constexpr int wheel_residues[] = {1, 7, 11, 13, 17, 19, 23, 29};

    // Visit the coprime-to-30 residues in ascending order, one 30-block at a time.
    for (int block = 0; block <= limit; block += 30) {
        for (const int residue : wheel_residues) {
            const int candidate = block + residue;
            if (candidate < 7 || candidate > limit) continue;

            bool prime = true;
            for (const int divisor : divisor_primes) {
                if (divisor * divisor > candidate) break;
                if (candidate % divisor == 0) {
                    prime = false;
                    break;
                }
            }

            if (prime) {
                sum += static_cast<std::uint64_t>(candidate);
                if (candidate <= limit / candidate) {
                    divisor_primes.push_back(candidate);
                }
            }
        }
    }

    std::cout << sum << '\n';
}
