#include <iostream>

#include "model.hpp"
#include "vehicle_model.hpp"

static params_dict_t parseYaml(char *path){
  return {};
}

int main(int argc, char *argv[]){
  if (argc != 1) {
    std::cout << "Please input a YAML config!" << std::endl;
    return -1;
  }

  params_dict_t params = parseYaml(argv[0]);

  VehicleModel *vm = new VehicleModel(params);
  // vm.add_model(new SCPArrayModel(params));
  // vm.add_model(new SCPBatteryModel(params));
  // vm.add_model(new SCPDragModel(params));
  // vm.add_model(new SCPRollingResistanceModel(params));

  delete vm;
}
