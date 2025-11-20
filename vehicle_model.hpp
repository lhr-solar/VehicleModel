#pragma once
#include "model.hpp"

class VehicleModel{
  public:
    VehicleModel(params_dict_t params);
    void add_model(Model m);
};
