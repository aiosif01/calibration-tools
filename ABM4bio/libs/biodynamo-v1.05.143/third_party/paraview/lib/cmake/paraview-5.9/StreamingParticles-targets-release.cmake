#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "StreamingParticles::vtkStreamingParticles" for configuration "Release"
set_property(TARGET StreamingParticles::vtkStreamingParticles APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(StreamingParticles::vtkStreamingParticles PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::FiltersCore;VTK::ParallelCore;VTK::RenderingCore;VTK::RenderingOpenGL2"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/StreamingParticles/libvtkStreamingParticles.so"
  IMPORTED_SONAME_RELEASE "libvtkStreamingParticles.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS StreamingParticles::vtkStreamingParticles )
list(APPEND _IMPORT_CHECK_FILES_FOR_StreamingParticles::vtkStreamingParticles "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/StreamingParticles/libvtkStreamingParticles.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
