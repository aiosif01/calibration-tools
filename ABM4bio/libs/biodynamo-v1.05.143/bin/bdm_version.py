# -----------------------------------------------------------------------------
#
# Copyright (C) 2021 CERN & University of Surrey for the benefit of the
# BioDynaMo collaboration. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# See the LICENSE file distributed with this work for details.
# See the NOTICE file distributed with this work for additional information
# regarding copyright ownership.
#
# -----------------------------------------------------------------------------

class Version:
    @staticmethod
    def string():
        return "v1.05.143-a9d3c90e"

    @staticmethod
    def shortstring():
        # python doesn't allow leading zeros in decimal numbers
        # -> use string to int conversion
        major = int('1')
        minor = int('05')
        patch = int('143')
        if patch == 0:
            return "{}.{}".format(major, minor)
        else:
            return "{}.{}.{}".format(major, minor, patch)

