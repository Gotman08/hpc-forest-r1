#include <algorithm>
#include <cstddef>
#include <iostream>
#include <utility>
#include <vector>

using namespace std;

static const long long MOD = 1000000007LL;

struct Point {
    int row;
    int col;
    long long ways;
};

static long long mod_pow(long long base, long long exponent) {
    long long result = 1;
    while (exponent > 0) {
        if (exponent & 1LL) result = result * base % MOD;
        base = base * base % MOD;
        exponent >>= 1LL;
    }
    return result;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) return 0;

    if (m == 0) {
        const int half_steps = n - 1;
        const int total_steps = 2 * half_steps;
        long long total_factorial = 1;
        long long half_factorial = 1;
        for (int i = 1; i <= total_steps; ++i) {
            total_factorial = total_factorial * i % MOD;
            if (i <= half_steps) half_factorial = half_factorial * i % MOD;
        }
        const long long inverse_half_factorial = mod_pow(half_factorial, MOD - 2);
        const long long answer = total_factorial * inverse_half_factorial % MOD *
                                 inverse_half_factorial % MOD;
        cout << answer << '\n';
        return 0;
    }

    vector<pair<int, int>> blocked;
    blocked.reserve(static_cast<size_t>(m));
    for (int i = 0; i < m; ++i) {
        int row, col;
        cin >> row >> col;
        blocked.emplace_back(row, col);
    }

    sort(blocked.begin(), blocked.end());
    blocked.erase(unique(blocked.begin(), blocked.end()), blocked.end());

    const pair<int, int> start{0, 0};
    const pair<int, int> finish{n - 1, n - 1};
    if (binary_search(blocked.begin(), blocked.end(), start) ||
        binary_search(blocked.begin(), blocked.end(), finish)) {
        cout << 0 << '\n';
        return 0;
    }

    const long long blocker_count = static_cast<long long>(blocked.size());
    const long long sparse_pairs = blocker_count * (blocker_count - 1) / 2;
    const long long grid_cells = static_cast<long long>(n) * n;

    if (sparse_pairs <= grid_cells / 4) {
        const int limit = 2 * n - 2;
        vector<long long> factorial(static_cast<size_t>(limit) + 1, 1);
        vector<long long> inverse_factorial(static_cast<size_t>(limit) + 1, 1);
        for (int i = 1; i <= limit; ++i) {
            factorial[static_cast<size_t>(i)] =
                factorial[static_cast<size_t>(i - 1)] * i % MOD;
        }
        inverse_factorial[static_cast<size_t>(limit)] =
            mod_pow(factorial[static_cast<size_t>(limit)], MOD - 2);
        for (int i = limit; i > 0; --i) {
            inverse_factorial[static_cast<size_t>(i - 1)] =
                inverse_factorial[static_cast<size_t>(i)] * i % MOD;
        }

        const auto choose = [&](int total, int selected) -> long long {
            if (selected < 0 || selected > total) return 0;
            return factorial[static_cast<size_t>(total)] *
                   inverse_factorial[static_cast<size_t>(selected)] % MOD *
                   inverse_factorial[static_cast<size_t>(total - selected)] % MOD;
        };

        vector<Point> points;
        points.reserve(blocked.size());
        for (const auto& cell : blocked) {
            points.push_back({cell.first, cell.second, 0});
        }

        for (size_t i = 0; i < points.size(); ++i) {
            Point& current = points[i];
            long long ways = choose(current.row + current.col, current.row);
            for (size_t j = 0; j < i; ++j) {
                const Point& previous = points[j];
                if (previous.row <= current.row && previous.col <= current.col) {
                    const int row_delta = current.row - previous.row;
                    const int col_delta = current.col - previous.col;
                    const long long paths = choose(row_delta + col_delta, row_delta);
                    ways -= previous.ways * paths % MOD;
                    if (ways < 0) ways += MOD;
                }
            }
            current.ways = ways;
        }

        long long answer = choose(2 * n - 2, n - 1);
        for (const Point& point : points) {
            const int row_delta = n - 1 - point.row;
            const int col_delta = n - 1 - point.col;
            const long long paths = choose(row_delta + col_delta, row_delta);
            answer -= point.ways * paths % MOD;
            if (answer < 0) answer += MOD;
        }
        cout << answer << '\n';
        return 0;
    }

    vector<int> dp(static_cast<size_t>(n), 0);
    dp[0] = 1;
    size_t obstacle_index = 0;
    for (int row = 0; row < n; ++row) {
        size_t row_end = obstacle_index;
        while (row_end < blocked.size() && blocked[row_end].first == row) ++row_end;

        size_t row_obstacle = obstacle_index;
        int next_col = 1;
        while (row_obstacle < row_end) {
            const int blocked_col = blocked[row_obstacle].second;
            while (next_col < blocked_col) {
                int ways = dp[static_cast<size_t>(next_col)] +
                           dp[static_cast<size_t>(next_col - 1)];
                if (ways >= MOD) ways -= static_cast<int>(MOD);
                dp[static_cast<size_t>(next_col)] = ways;
                ++next_col;
            }

            dp[static_cast<size_t>(blocked_col)] = 0;
            if (blocked_col >= next_col) next_col = blocked_col + 1;
            ++row_obstacle;
        }

        while (next_col < n) {
            int ways = dp[static_cast<size_t>(next_col)] +
                       dp[static_cast<size_t>(next_col - 1)];
            if (ways >= MOD) ways -= static_cast<int>(MOD);
            dp[static_cast<size_t>(next_col)] = ways;
            ++next_col;
        }
        obstacle_index = row_end;
    }

    cout << dp[static_cast<size_t>(n - 1)] << '\n';
    return 0;
}
