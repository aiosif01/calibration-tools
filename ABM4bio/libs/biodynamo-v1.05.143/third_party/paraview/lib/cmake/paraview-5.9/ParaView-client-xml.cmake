set(_vtk_module_import_prefix "${CMAKE_CURRENT_LIST_DIR}")
get_filename_component(_vtk_module_import_prefix "${_vtk_module_import_prefix}" DIRECTORY)
get_filename_component(_vtk_module_import_prefix "${_vtk_module_import_prefix}" DIRECTORY)
get_filename_component(_vtk_module_import_prefix "${_vtk_module_import_prefix}" DIRECTORY)
set("${CMAKE_FIND_PACKAGE_NAME}_CLIENT_XML_FILES")
list(APPEND "${CMAKE_FIND_PACKAGE_NAME}_CLIENT_XML_FILES"
  "${_vtk_module_import_prefix}/share/paraview-5.9/xmls/ParaViewFilters.xml")
list(APPEND "${CMAKE_FIND_PACKAGE_NAME}_CLIENT_XML_FILES"
  "${_vtk_module_import_prefix}/share/paraview-5.9/xmls/ParaViewSources.xml")
