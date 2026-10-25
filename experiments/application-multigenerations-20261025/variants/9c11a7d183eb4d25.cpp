#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

namespace {
constexpr int kWheelResidues[8] = {1, 7, 11, 13, 17, 19, 23, 29};
constexpr int kWheelGaps[8] = {6, 4, 2, 4, 2, 4, 6, 2};
constexpr int kSlotByRemainder[30] = {
    -1, 0, -1, -1, -1, -1, -1, 1, -1, -1,
    -1, 2, -1, 3, -1, -1, -1, 4, -1, 5,
    -1, -1, -1, 6, -1, -1, -1, -1, -1, 7};

std::size_t wheel_index(int value) {
    return static_cast<std::size_t>(value / 30) * 8 +
           static_cast<std::size_t>(kSlotByRemainder[value % 30]);
}
}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const int limit = std::atoi(argv[1]);
    if (limit < 0 || limit > 200000) return 2;

    const int remainder = limit % 30;
    std::size_t slot_count = static_cast<std::size_t>(limit / 30) * 8;
    for (int slot = 0;
         slot < 8 && kWheelResidues[slot] <= remainder;
         ++slot) {
        ++slot_count;
    }

    std::vector<unsigned char> composite(slot_count, 0);
    if (!composite.empty()) composite[0] = 1;  // 1 is not prime.

    for (std::size_t index = 1; index < slot_count; ++index) {
        const int p = static_cast<int>(index / 8) * 30 +
                      kWheelResidues[index % 8];
        if (p > limit / p) break;
        if (composite[index]) continue;

        const int quotient_limit = limit / p;
        int wheel_slot = static_cast<int>(index % 8);
        for (int quotient = p; quotient <= quotient_limit;
             quotient += kWheelGaps[wheel_slot], wheel_slot = (wheel_slot + 1) % 8) {
            const int value = p * quotient;
            composite[wheel_index(value)] = 1;
        }
    }

    std::uint64_t sum = 0;
    if (limit >= 2) sum += 2;
    if (limit >= 3) sum += 3;
    if (limit >= 5) sum += 5;
    for (std::size_t index = 1; index < slot_count; ++index) {
        if (!composite[index]) {
            const int value = static_cast<int>(index / 8) * 30 +
                              kWheelResidues[index % 8];
            sum += static_cast<std::uint64_t>(value);
        }
    }

    std::cout << sum << '\n';
}
