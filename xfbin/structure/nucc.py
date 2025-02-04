from enum import IntFlag
from typing import Dict, Iterator, List, Optional, Set

from ..util import *
from .anm import AnmClump, AnmEntry
from .br.br_nucc import *
from .br.br_nud import *
from .br.br_nut import *
from .nud import Nud


class NuccChunk:
    filePath: str
    name: str
    data: bytearray

    extension: str

    chunks: List['NuccChunk']

    def __init__(self, file_path, name):
        self.extension = ''
        self.filePath = file_path
        self.name = name

        self.has_data = False
        self.has_props = False
        self.chunks = list()

    def set_data(self, data: bytearray, chunks):
        self.data = data
        self.has_data = True

        self.chunks = [c for c in chunks if not isinstance(c, (NuccChunkPage, NuccChunkIndex))]

    def init_data(self, br_chunk: BrNuccChunk, chunk_list: List['NuccChunk'], chunk_indices: List[int], chunk_refs: List['ChunkReference']):
        """Initializes the data of this `NuccChunk` from a `BrNuccChunk`, using a chunk list and a list of
        local page indices for properly setting references to other `NuccChunk`s
        """
        self.data = br_chunk.data
        self.has_data = True

        # Temporary way to store referenced chunks for rebuilding
        # TODO: Maybe replace this with a better solution later
        self.chunks = [chunk_list[x]
                       for x in chunk_indices if not isinstance(chunk_list[x], (NuccChunkPage, NuccChunkIndex))]

    def get_data(self, file_data_only: bool) -> bytearray:
        """Returns the data of this chunk when it was first read from the XFBIN as a buffer.\n
        If file_data_only is True, will return only the data contained in the formatted file of the chunk.
        (NTP3 .nut for nuccChunkTexture, NDP3 .nud for nuccChunkModel)
        """
        if file_data_only and hasattr(self, 'file_data'):
            return getattr(self, 'file_data')

        return self.data

    def to_dict(self) -> Dict[str, str]:
        d = dict()
        d['Name'] = self.name
        d['Type'] = NuccChunk.get_nucc_str_from_type(type(self))
        d['Path'] = self.filePath

        return d

    @classmethod
    def get_nucc_type_from_str(cls, type_str: str) -> type:
        type_name = type_str[0].upper() + type_str[1:]
        result = globals().get(type_name, None)

        if result is None:
            # Create a new type and add it to the globals
            result = type(type_name, (cls,), {})
            globals()[type_name] = result

        return result

    @classmethod
    def get_nucc_str_from_type(cls, nucc_type: type) -> str:
        return nucc_type.__name__[0].lower() + nucc_type.__name__[1:]

    @classmethod
    def get_nucc_str_short_from_type(cls, nucc_type: type) -> str:
        return cls.get_nucc_str_from_type(nucc_type)[len(NuccChunk.__qualname__):]

    @classmethod
    def create_from_nucc_type(cls, type_str, file_path, name) -> 'NuccChunk':
        return cls.get_nucc_type_from_str(type_str)(file_path, name)

    @classmethod
    def get_all_nucc_types(cls):
        # This will only return types with names that start with this class's name (but are not this class)
        return [n for (k, n) in globals() if k.startswith(cls.__qualname__) and len(k) > len(cls.__qualname__)]

    def __eq__(self, o: object) -> bool:
        # Treat NuccChunks as ChunkMaps:
        # ChunkMaps are only equal to other ChunkMaps that have the same type, file path, and name
        return isinstance(o, type(self)) and self.filePath == o.filePath and self.name == o.name

    def __hash__(self) -> int:
        # Just a simple hash calculation to allow NuccChunks to be put into a dictionary
        return hash(type(self).__qualname__) ^ hash(self.filePath) ^ hash(self.name)


class NuccChunkNull(NuccChunk):
    # Empty
    def __init__(self, file_path='', name=''):
        super().__init__(file_path, name)
        self.has_props = True


class NuccChunkPage(NuccChunk):
    # Should not be used as a NuccChunk, except when writing
    def __init__(self, file_path='', name='Page0'):
        super().__init__(file_path, name)
        self.has_props = True


class NuccChunkIndex(NuccChunk):
    # Does not exist
    def __init__(self, file_path='', name='index'):
        super().__init__(file_path, name)
        self.has_props = True


class NuccChunkTexture(NuccChunk):
    def __init__(self, file_path, name):
        super().__init__(file_path, name)

        # Set these to None in case a texture is a reference only and isn't contained in the xfbin
        self.data = self.nut = None

    def init_data(self, br_chunk: BrNuccChunkTexture, chunk_list: List['NuccChunk'], chunk_indices: List[int], chunk_refs: List['ChunkReference']):
        self.extension = '.nut'

        self.data = br_chunk.data
        self.has_data = True
        self.has_props = True

        self.width = br_chunk.width
        self.height = br_chunk.width

        # Since Nut support has not been added yet, this will be written instead of the Nut object
        self.file_data = br_chunk.nut_data

        # TODO: Implement Nut
        #self.nut = Nut(br_chunk.brNut)


class NuccChunkDynamics(NuccChunk):
    def init_data(self, br_chunk: BrNuccChunkDynamics, chunk_list: List['NuccChunk'], chunk_indices: List[int], chunk_refs: List['ChunkReference']):
        self.data = br_chunk.data
        self.has_data = True
        self.has_props = True

        self.clump_chunk: NuccChunkClump = chunk_list[chunk_indices[br_chunk.clumpChunkIndex]]

        # Make an iterator to give each Dynamics1 entry its own values
        sec1_shorts = iter(br_chunk.section1Shorts)

        self.section1: List[Dynamics1] = list()
        for sec1 in br_chunk.section1:
            d = Dynamics1()
            d.init_data(sec1, sec1_shorts)
            self.section1.append(d)

        self.section2: List[Dynamics2] = list()
        for sec2 in br_chunk.section2:
            d = Dynamics2()
            d.init_data(sec2)
            self.section2.append(d)


class Dynamics1:
    def init_data(self, sec1: BrDynamics1, sec1_shorts: Iterator):
        self.floats = sec1.floats
        self.coord_index = sec1.coordIndex

        self.shorts = list()
        for _ in range(sec1.unkCount):
            self.shorts.append(next(sec1_shorts))


class Dynamics2:
    def init_data(self, sec2: BrDynamics2):
        self.floats = sec2.floats
        self.coord_index = sec2.coordIndex

        # Should always be -1, but let's store it just in case
        self.negative_unk = sec2.negativeUnk

        self.unk_short_tuples = list(sec2.unkShortTuples)


class NuccChunkClump(NuccChunk):
    def init_data(self, br_chunk: BrNuccChunkClump, chunk_list: List['NuccChunk'], chunk_indices: List[int], chunk_refs: List['ChunkReference']):
        self.data = br_chunk.data
        self.has_data = True
        self.has_props = True

        self.field00 = br_chunk.field00

        self.coord_flag0 = br_chunk.coordFlag0
        self.coord_flag1 = br_chunk.coordFlag1

        self.model_flag0 = br_chunk.modelFlag0
        self.model_flag1 = br_chunk.modelFlag1

        # Get the coord chunks
        self.coord_chunks: List[NuccChunkCoord] = list()
        for i in br_chunk.coordNodeIndices:
            self.coord_chunks.append(chunk_list[chunk_indices[i]])

        # Setup the coord node hierarchy
        self.root_nodes: List[CoordNode] = list()
        for i, j in zip(range(len(self.coord_chunks)), br_chunk.coordNodeParentsIndices):
            if j == -1:
                # There could be multiple root nodes: add all of them
                self.root_nodes.append(self.coord_chunks[i].node)
            else:
                # Set the node's parent and add the node to its parent's children
                self.coord_chunks[i].node.parent = self.coord_chunks[j].node
                self.coord_chunks[j].node.children.append(self.coord_chunks[i].node)

        # Get the model chunks
        self.model_chunks: List[NuccChunkModel] = list()
        for i in br_chunk.modelIndices:
            model: NuccChunkModel = chunk_list[chunk_indices[i]]
            self.model_chunks.append(model)

            # There are other types of chunks that can be used as models (Billboard for example)
            if isinstance(model, NuccChunkModel):
                # Set the model chunk's respective coord
                if model.coord_index != -1:
                    model.coord_chunk = self.coord_chunks[model.coord_index]

        # Initialize the model groups
        self.model_groups: List[ClumpModelGroup] = list()
        for model_group in br_chunk.modelGroups:
            self.model_groups.append(ClumpModelGroup())
            self.model_groups[-1].init_data(model_group, self.coord_chunks, chunk_list, chunk_indices)

    def clear_non_model_chunks(self, model_list: bool = True, model_groups: bool = True, none_refs: bool = False) -> int:
        """Removes all chunks that are not NuccChunkModel from the model list and model groups of this clump, based on the arguments.\n
        If none_refs is True, will also remove "None" entries.\n
        Returns the number of chunks removed, including duplicates.
        """

        org_count = len(self.model_chunks) + sum(list(map(lambda x: len(x.model_chunks), self.model_groups)))

        if model_list:
            self.model_chunks = [x for x in self.model_chunks if isinstance(
                x, NuccChunkModel) or ((x is None) if (not none_refs) else False)]

        if model_groups:
            for group in self.model_groups:
                group.model_chunks = [x for x in group.model_chunks if isinstance(
                    x, NuccChunkModel) or ((x is None) if (not none_refs) else False)]

        return org_count - (len(self.model_chunks) + sum(list(map(lambda x: len(x.model_chunks), self.model_groups))))


class ClumpModelGroup:
    def __init__(self) -> None:
        self.model_chunks: List[NuccChunkModel] = list()

    def init_data(self, model_group: BrClumpModelGroup, coord_chunks: List['NuccChunkCoord'], chunk_list: List['NuccChunk'], chunk_indices: List[int]):
        self.flag0 = model_group.flag0
        self.flag1 = model_group.flag1
        self.unk = model_group.unk

        self.model_chunks: List[NuccChunkModel] = list(
            map(lambda x: chunk_list[chunk_indices[x]] if x != -1 else None, model_group.modelIndices))

        for chunk in self.model_chunks:
            # Set the model chunk's respective coord
            if chunk and chunk.coord_index != -1:
                chunk.coord_chunk = coord_chunks[chunk.coord_index]

    def __iter__(self):
        return iter(self.model_chunks)


class NuccChunkCoord(NuccChunk):
    def init_data(self, br_chunk: BrNuccChunkCoord, chunk_list: List['NuccChunk'], chunk_indices: List[int], chunk_refs: List['ChunkReference']):
        self.data = br_chunk.data
        self.has_data = True
        self.has_props = True

        # Pass a reference to the chunk itself for accessing it later
        self.node = CoordNode(self)
        self.node.init_data(br_chunk)


class CoordNode:
    parent: Optional['CoordNode']
    children: List['CoordNode']

    def __init__(self, chunk: NuccChunkCoord):
        self.chunk = chunk

        self.name = chunk.name
        self.parent = None
        self.children = list()

        self.position = (0.0,) * 3
        self.rotation = (0.0,) * 3
        self.scale = (1.0,) * 3
        self.unkFloat = 1.0
        self.unkShort = 0

    def init_data(self, coord: BrNuccChunkCoord):
        self.position = coord.position
        self.rotation = coord.rotation
        self.scale = coord.scale
        self.unkFloat = coord.unkFloat
        self.unkShort = coord.unkShort

    def get_children_recursive(self) -> List['CoordNode']:
        result = list()

        for child in self.children:
            result.extend(child.get_children_recursive())

        return result

    def copy_from(self, other: 'CoordNode'):
        """Copies the contents of another node into this node without changing the parenting relations."""

        self.position = other.position
        self.rotation = other.rotation
        self.scale = other.scale
        self.unkFloat = other.unkFloat
        self.unkShort = other.unkShort


class NuccChunkModel(NuccChunk):
    def init_data(self, br_chunk: BrNuccChunkModel, chunk_list: List['NuccChunk'], chunk_indices: List[int], chunk_refs: List['ChunkReference']):
        self.extension = '.nud'

        self.data = br_chunk.data
        self.has_data = True
        self.has_props = True

        # Store the rigging flag to use when writing, if the rigging flag was not specified while exporting
        self.rigging_flag = RiggingFlag(br_chunk.riggingFlag)

        # Get the transparency/shading flags
        self.material_flags: List[int] = br_chunk.materialFlags
        self.flag1_floats = br_chunk.flag1Floats if self.material_flags[1] & 0x04 else tuple()

        # Reference to the clump chunk of this page
        self.clump_chunk = chunk_list[chunk_indices[br_chunk.clumpIndex]]

        # Reference to the ModelHit chunk of this model
        self.hit_chunk = chunk_list[chunk_indices[br_chunk.hitIndex]]

        # This will be set later in the clump, using the index
        self.coord_chunk: Optional[NuccChunkCoord] = None

        # This should be set again when creating a new instance, instead of getting it from the clump when writing
        self.coord_index = br_chunk.meshBoneIndex

        self.file_data = br_chunk.nud_data

        # Create a Nud from the BrNud
        self.nud = Nud()
        self.nud.init_data(self.name, br_chunk.brNud)

        # Get the material chunks
        self.material_chunks: List[NuccChunkMaterial] = list()
        for i in br_chunk.materialIndices:
            self.material_chunks.append(chunk_list[chunk_indices[i]])

    def copy_from(self, other: 'NuccChunkModel'):
        """Copies the contents of another chunk to this chunk (shallow copy).\n
        Used for modifying a chunk without losing its original reference inside other chunks.
        """

        if hasattr(other, 'data'):
            self.data = other.data

        self.extension = other.extension

        self.rigging_flag = other.rigging_flag
        self.material_flags = other.material_flags
        self.flag1_floats = other.flag1_floats

        self.clump_chunk = other.clump_chunk

        # TODO: Remove this check once NuccChunkModelHit is imported into blender
        # This prevents us from overwriting an existing hit chunk with a null chunk
        if other.hit_chunk and not isinstance(other.hit_chunk, NuccChunkNull):
            self.hit_chunk = other.hit_chunk

        self.coord_chunk = other.coord_chunk
        self.coord_index = other.coord_index

        self.nud = other.nud
        self.material_chunks = other.material_chunks


class RiggingFlag(IntFlag):
    NULL = 0x0

    UNSKINNED = 0x01  # Storm eyes and JoJo teeth
    SKINNED = 0x02  # JoJo eyes
    BODY = 0x04

    TEETH = 0x05  # Storm teeth
    FULL = 0x06  # Body and tongue

    # Storm 4 and JoJo use these two combined for most models (in addition to the previous flags)
    BLUR = 0x10
    SHADOW = 0x20


class NuccChunkMaterial(NuccChunk):
    def init_data(self, br_chunk: BrNuccChunkMaterial, chunk_list: List['NuccChunk'], chunk_indices: List[int], chunk_refs: List['ChunkReference']):
        self.data = br_chunk.data
        self.has_data = True
        self.has_props = True

        self.field02 = br_chunk.field02
        self.field04 = br_chunk.field04

        self.format = br_chunk.format
        self.floats = br_chunk.floats

        self.texture_groups: List[MaterialTextureGroup] = list()
        for group in br_chunk.textureGroups:
            g = MaterialTextureGroup()
            g.init_data(group, chunk_list, chunk_indices)
            self.texture_groups.append(g)

    # Wrapper method
    @staticmethod
    def float_count(format) -> int:
        return BrNuccChunkMaterial.float_count(format)

    def __iter__(self):
        all_textures: Set[NuccChunkTexture] = set()

        for group in self.texture_groups:
            all_textures.update(group.texture_chunks)

        return iter(all_textures)


class MaterialTextureGroup:
    def init_data(self, texture_group: BrMaterialTextureGroup, chunk_list: List['NuccChunk'], chunk_indices: List[int]):
        self.unk = texture_group.unk

        self.texture_chunks: List[NuccChunkTexture] = list()
        for index in texture_group.textureIndices:
            self.texture_chunks.append(chunk_list[chunk_indices[index]])

    def __iter__(self):
        return iter(self.texture_chunks)


class NuccChunkAnm(NuccChunk):
    def init_data(self, br_chunk: BrNuccChunkAnm, chunk_list: List['NuccChunk'], chunk_indices: List[int], chunk_refs: List['ChunkReference']):
        self.data = br_chunk.data
        self.has_data = True
        self.has_props = True

        self.anm_length = br_chunk.anm_length
        self.frame_size = br_chunk.frame_size

        # Set up the clumps
        self.clumps: List[AnmClump] = list()
        for br_anm_clump in br_chunk.clumps:
            anm_clump = AnmClump()
            anm_clump.init_data(br_anm_clump, chunk_refs)
            self.clumps.append(anm_clump)

        # Set up the child-parent relations in AnmBones
        for p in br_chunk.coord_parents:
            if -1 in [p.parent_clump_index, p.parent_coord_index, p.child_clump_index, p.child_coord_index]:
                continue
            
            p: BrAnmCoordParent
            parent = self.clumps[p.parent_clump_index].bones[p.parent_coord_index]
            child = self.clumps[p.child_clump_index].bones[p.child_coord_index]
            child.parent = parent
            parent.children.append(child)

        other_entry_chunks = list(map(lambda x: chunk_list[chunk_indices[x]], br_chunk.other_entry_indices))

        # Set up the animation entries/bones
        self.entries: List[AnmEntry] = [None] * len(br_chunk.entries)
        for i, br_entry in enumerate(br_chunk.entries):
            entry = self.entries[i] = AnmEntry()
            entry.init_data(br_entry, self.frame_size, self.clumps, other_entry_chunks)

        # Get the "other" entries from the entry list
        self.other_entries = [e for e in self.entries if e.clump is None]
