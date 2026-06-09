{
  gROOT->ProcessLine("#define USE_DICT");
  gROOT->ProcessLine("R__ADD_INCLUDE_PATH($BDMSYS/include)");
  gROOT->ProcessLine("R__ADD_LIBRARY_PATH($BDMSYS/lib)");
  gROOT->ProcessLine("R__LOAD_LIBRARY(libbiodynamo)");
  gROOT->ProcessLine("R__LOAD_LIBRARY(GenVector)");
  gROOT->ProcessLine("#include \"biodynamo.h\"");
  gROOT->ProcessLine("using namespace bdm;");
  gROOT->ProcessLine("Simulation simulation(\"simulation\");");
  gROOT->ProcessLine("cout << \"INFO: Created simulation object 'simulation' with UniqueName='simulation'.\" << endl;");
}
