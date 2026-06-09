#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "MooseXfemClip::vtkMooseXfemClip" for configuration "Release"
set_property(TARGET MooseXfemClip::vtkMooseXfemClip APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MooseXfemClip::vtkMooseXfemClip PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/MooseXfemClip/libvtkMooseXfemClip.so"
  IMPORTED_SONAME_RELEASE "libvtkMooseXfemClip.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS MooseXfemClip::vtkMooseXfemClip )
list(APPEND _IMPORT_CHECK_FILES_FOR_MooseXfemClip::vtkMooseXfemClip "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/MooseXfemClip/libvtkMooseXfemClip.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
