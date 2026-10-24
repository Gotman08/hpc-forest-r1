CC = gcc
CFLAGS = -O3 -std=c11 -fopenmp

.PHONY: all clean
all: solution

solution: src/main.c src/params.h
	$(CC) $(CFLAGS) src/main.c -o solution

clean:
	rm -f solution
