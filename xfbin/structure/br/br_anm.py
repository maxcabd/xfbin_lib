from enum import IntEnum

from ...util import *


class BrAnmClump(BrStruct):
    def __br_read__(self, br: 'BinaryReader'):
        self.clump_index = br.read_uint32()

        self.bone_count = br.read_uint16()  # Including materials
        self.model_count = br.read_uint16()

        self.bones = br.read_uint32(self.bone_count)
        self.models = br.read_uint32(self.model_count)


class BrAnmCoordParent(BrStruct):
    def __br_read__(self, br: 'BinaryReader'):
        self.parent_clump_index = br.read_int16()
        self.parent_coord_index = br.read_uint16()

        self.child_clump_index = br.read_int16()
        self.child_coord_index = br.read_uint16()


class AnmEntryFormat(IntEnum):
    BONE = 1
    CAMERA = 2
    MATERIAL = 4
    LIGHTDIRC = 5
    LIGHTPOINT = 6


class AnmCurveFormat(IntEnum):
    FLOAT3 = 0x05  # location/scale
    INT1_FLOAT3 = 0x06  # location/scale (with keyframe)
    FLOAT3ALT = 0x08  # rotation
    INT1_FLOAT4 = 0x0A  # rotation quaternions (with keyframe)
    FLOAT1 = 0x0B  # "toggled"
    INT1_FLOAT1 = 0x0C  # camera
    SHORT1 = 0x0F  # "toggled"
    SHORT3 = 0x10  # scale
    SHORT4 = 0x11  # rotation quaternions
    BYTE3 = 0x14  # lightdirc
    FLOAT3ALT2 = 0x15  # scale
    FLOAT1ALT = 0x16  # lightdirc
    FLOAT1ALT2 = 0x18  # material


class BrAnmCurveHeader(BrStruct):
    def __br_read__(self, br: 'BinaryReader'):
        self.curve_index = br.read_uint16()  # Might be used for determining the order of curves
        self.curve_format = br.read_uint16()
        self.keyframe_count = br.read_uint16()
        self.curve_flags = br.read_int16()


class BrAnmEntry(BrStruct):
    def __br_read__(self, br: 'BinaryReader'):
        self.clump_index = br.read_int16()
        self.bone_index = br.read_uint16()

        self.entry_format = br.read_uint16()
        self.curve_count = br.read_uint16()

        self.curve_headers = br.read_struct(BrAnmCurveHeader, self.curve_count)

        self.curves = list()
        for header in self.curve_headers:
            # Some mini optimizations
            curve = [None] * header.keyframe_count

            # More mini optimizations that make the code a lot less readable
            if header.curve_format == AnmCurveFormat.FLOAT3:  # 0x05
                for i in range(header.keyframe_count):
                    curve[i] = br.read_float(3)

            elif header.curve_format == AnmCurveFormat.INT1_FLOAT3:  # 0x06
                for i in range(header.keyframe_count):
                    curve[i] = (br.read_int32(), *br.read_float(3))

            elif header.curve_format == AnmCurveFormat.FLOAT3ALT:  # 0x08
                for i in range(header.keyframe_count):
                    curve[i] = br.read_float(3)

            elif header.curve_format == AnmCurveFormat.INT1_FLOAT4:  # 0x0A
                for i in range(header.keyframe_count):
                    curve[i] = (br.read_int32(), *br.read_float(4))

            elif header.curve_format == AnmCurveFormat.FLOAT1:  # 0x0B
                for i in range(header.keyframe_count):
                    curve[i] = br.read_float(1)

            elif header.curve_format == AnmCurveFormat.INT1_FLOAT1:  # 0x0C
                for i in range(header.keyframe_count):
                    curve[i] = (br.read_int32(), br.read_float())

            elif header.curve_format == AnmCurveFormat.SHORT1:  # 0x0F
                for i in range(header.keyframe_count):
                    curve[i] = br.read_int16(1)

            elif header.curve_format == AnmCurveFormat.SHORT3:  # 0x10
                for i in range(header.keyframe_count):
                    curve[i] = br.read_int16(3)

            elif header.curve_format == AnmCurveFormat.SHORT4:  # 0x11
                for i in range(header.keyframe_count):
                    curve[i] = br.read_int16(4)

            elif header.curve_format == AnmCurveFormat.BYTE3:  # 0x14
                for i in range(header.keyframe_count):
                    curve[i] = br.read_int8(3)

            elif header.curve_format == AnmCurveFormat.FLOAT3ALT2:  # 0x15
                for i in range(header.keyframe_count):
                    curve[i] = br.read_float(3)

            elif header.curve_format == AnmCurveFormat.FLOAT1ALT:  # 0x16
                for i in range(header.keyframe_count):
                    curve[i] = br.read_float(1)

            elif header.curve_format == AnmCurveFormat.FLOAT1ALT2:  # 0x18
                for i in range(header.keyframe_count):
                    curve[i] = br.read_float(1)

            else:
                raise Exception('nuccChunkAnm: Unsupported curve format')

            br.align_pos(4)

            self.curves.append(curve)
