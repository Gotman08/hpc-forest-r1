all: build/solution
build/solution: src/candidate.cu
	mkdir -p build
	nvcc -std=c++17 -O3 -arch=sm_90 -shared -Xcompiler=-fPIC $< -o $@
