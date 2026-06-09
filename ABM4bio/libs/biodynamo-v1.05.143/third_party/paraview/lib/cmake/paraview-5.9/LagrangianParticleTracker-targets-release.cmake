#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "LagrangianParticleTracker::vtkLagrangianParticleTracker" for configuration "Release"
set_property(TARGET LagrangianParticleTracker::vtkLagrangianParticleTracker APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(LagrangianParticleTracker::vtkLagrangianParticleTracker PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel;VTK::FiltersFlowPaths"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/LagrangianParticleTracker/libvtkLagrangianParticleTracker.so"
  IMPORTED_SONAME_RELEASE "libvtkLagrangianParticleTracker.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS LagrangianParticleTracker::vtkLagrangianParticleTracker )
list(APPEND _IMPORT_CHECK_FILES_FOR_LagrangianParticleTracker::vtkLagrangianParticleTracker "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/LagrangianParticleTracker/libvtkLagrangianParticleTracker.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
