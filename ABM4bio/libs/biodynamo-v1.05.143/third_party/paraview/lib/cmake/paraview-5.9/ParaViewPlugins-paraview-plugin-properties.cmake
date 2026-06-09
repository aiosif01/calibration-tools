set(_vtk_module_import_prefix "${CMAKE_CURRENT_LIST_DIR}")
get_filename_component(_vtk_module_import_prefix "${_vtk_module_import_prefix}" DIRECTORY)
get_filename_component(_vtk_module_import_prefix "${_vtk_module_import_prefix}" DIRECTORY)
get_filename_component(_vtk_module_import_prefix "${_vtk_module_import_prefix}" DIRECTORY)
set_property(TARGET "ParaView::paraview_plugins"
  PROPERTY
    INTERFACE_paraview_plugin_plugins_file "${_vtk_module_import_prefix}/lib/paraview-5.9/plugins/paraview.plugins.xml")
unset(_vtk_module_import_prefix)
