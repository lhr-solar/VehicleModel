# Compiler and flags
CXX := g++
CXXFLAGS := -Wall -Wextra -std=c++17 -O2

# Target name (executable)
TARGET := vmod

# Build directory
BUILD := build

# Source files (all .cpp in current dir)
SRC := $(wildcard *.cpp)

# Object files (in build/)
OBJ := $(patsubst %.cpp,$(BUILD)/%.o,$(SRC))

all: $(BUILD) $(BUILD)/$(TARGET)

# Link final executable
$(BUILD)/$(TARGET): $(OBJ)
	$(CXX) $(CXXFLAGS) -o $@ $^
	chmod +x $@

# Compile each .cpp → build/.o
$(BUILD)/%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Create build directory
$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD)

.PHONY: all clean
