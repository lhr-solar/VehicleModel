#pragma once

#include <string>
#include <unordered_map>

typedef std::unordered_map<std::string, float> params_dict_t;

class Model {
  private:
    params_dict_t params;
    
  public:
    
};
