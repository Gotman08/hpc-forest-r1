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
    if (limit >= 2) { primes.push_back(2); sum += 2; }
    if (limit >= 3) { primes.push_back(3); sum += 3; }
    if (limit >= 5) { primes.push_back(5); sum += 5; }
    if (limit >= 7) { primes.push_back(7); sum += 7; }

    // Residues coprime to 210, in ascending order.
    const int residues[] = {
        1, 11, 13, 17, 19, 23, 29,
        31, 37, 41, 43, 47, 53, 59,
        61, 67, 71, 73, 79, 83, 89,
        97, 101, 103, 107, 109, 113,
        121, 127, 131, 137, 139, 143, 149,
        151, 157, 163, 167, 169, 173, 179,
        181, 187, 191, 193, 197, 199, 209
    };

    for (int block_base = 0; block_base <= limit; block_base += 210) {
        for (int offset : residues) {
            const int candidate = block_base + offset;
            if (candidate > limit) break;
            if (candidate < 11) continue;

            bool prime = true;
            for (std::size_t i = 4; i < primes.size(); ++i) {
                const int divisor = primes[i];
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
        }
    }

    std::cout << sum << '\n';
}
