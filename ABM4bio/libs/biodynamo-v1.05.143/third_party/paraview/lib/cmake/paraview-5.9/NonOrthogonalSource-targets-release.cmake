#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "NonOrthogonalSource::vtkNonOrthogonalSources" for configuration "Release"
set_property(TARGET NonOrthogonalSource::vtkNonOrthogonalSources APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(NonOrthogonalSource::vtkNonOrthogonalSources PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "ParaView::VTKExtensionsMisc;VTK::CommonCore;VTK::CommonDataModel;VTK::CommonMath;VTK::CommonTransforms;VTK::FiltersGeneral;VTK::ImagingCore"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/NonOrthogonalSource/libvtkNonOrthogonalSources.so"
  IMPORTED_SONAME_RELEASE "libvtkNonOrthogonalSources.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS NonOrthogonalSource::vtkNonOrthogonalSources )
list(APPEND _IMPORT_CHECK_FILES_FOR_NonOrthogonalSource::vtkNonOrthogonalSources "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/NonOrthogonalSource/libvtkNonOrthogonalSources.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
