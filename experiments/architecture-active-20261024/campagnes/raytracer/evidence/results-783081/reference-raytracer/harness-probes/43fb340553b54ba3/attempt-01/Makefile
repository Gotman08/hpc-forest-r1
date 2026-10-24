all: build/solution
build/solution: src/candidate.cpp
	mkdir -p build
	g++ -std=c++17 -O3 -march=native -fPIC -shared -fopenmp -Wl,-Bsymbolic -Iinclude $< -o $@
