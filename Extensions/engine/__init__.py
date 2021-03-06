import multiprocessing
import chunks
from os.path import abspath
import numpy as np
import pyrr

from OpenGL.GL import *
from pyrr import vector

from Extensions import loaders
from math import sin, cos, radians, floor

import chunks
# import multiprocessing
# import threading
import concurrent.futures

# objects = []
TEXTURE_ATLAS = loaders.TextureAtlas(abspath('Assets/Textures/minecraft_texture_sheet.png'), 48)

# Vector3 
class Vector3:
    zero = pyrr.Vector3([0, 0, 0], dtype=float)
    up = pyrr.Vector3([0, 1, 0], dtype=float)
    forward = pyrr.Vector3([0, 0, 1], dtype=float)
    right = pyrr.Vector3([1, 0, 0], dtype=float)

    @staticmethod
    def isZero(vector3):
        """
        Check if array / vector is all zeros
        returns:
            True if is all zeros
        """
        condition = True

        for x in vector3:
            condition &= not x
        
        return condition

    @staticmethod
    def isZero(vector3, callback):
        condition = True
        for x in vector3:
            condition &= not x
        
        if not condition:
            return callback()
        
        return vector3



class Transform:
    """
    COMPONENT,
    keeps track of object position and rotation
    """
    def __init__(self, position:tuple or list=(0, 2, 0), rotation: tuple or list=(0, 0, 0)):
        self._position = pyrr.Vector3(position, dtype=float)
        self._rotation = pyrr.Vector3(rotation, dtype=float)
        self._parent = None

    #region Properties
    @property
    def position(self):
        return self._position

    @property
    def rotation(self):
        return pyrr.Quaternion.from_eulers(self._rotation)

    @property
    def eulers(self):
        return self._rotation

    @property
    def parent(self):
        return self._parent
    #endregion

    #region Setters
    @position.setter
    def position(self, new_postion):
        self.move_to_position(new_postion)

    @rotation.setter
    def rotation(self, new_eulers):
        self.rotate_to(new_eulers)
    #endregion

    #region Functions
    #region Movement
    def move(self, direction: tuple or list):
        direction = pyrr.Vector3(direction, dtype=float)
        self._position += direction

    def move_to(self, new_position: tuple or list):
        new_position = pyrr.Vector3(new_position, dtype=float)
        self._position = new_position

    # def move_look_at(self, direction: tuple or list, target: tuple or list=(0, 0, 0)):
    #     direction = pyrr.Vector3(direction)
    #     target = pyrr.Vector3(target)
    #     self.view = pyrr.matrix44.create_look_at(self.position + direction, target, self.up)
    #endregion

    #region Rotation
    def rotate(self, rotation: tuple or list):
        rotation = pyrr.Vector3(rotation, dtype=float)
        self._rotation += rotation

    def rotate_to(self, new_rotation: tuple or list):
        new_rotation = pyrr.Vector3(new_rotation, dtype=float)
        self._rotation = new_rotation
    #endregion
    #endregion



class ChunkRenderer:
    """
    Storing array of active chunks \n
    functions:
        __init__: intialization
        create_buffers: this is called in __init__, if it isn't specified otherwise
        render: renders object
    """
    ACTIVE_AREA_EDGE = 5
    ACTIVE_AREA_SIZE = pyrr.Vector3([ACTIVE_AREA_EDGE, 1, ACTIVE_AREA_EDGE])
    ACTIVE_AREA_HALF = (ACTIVE_AREA_SIZE - 1) // 2
    ACTIVE_AREA_yz = ACTIVE_AREA_SIZE.y * ACTIVE_AREA_SIZE.z 
    ACTIVE_AREA_INDEX_VECTOR = pyrr.Vector3([ACTIVE_AREA_yz, ACTIVE_AREA_SIZE.z, 1])

    def __init__(self, position:tuple[3] or list[3]=(0, 0, 0), atlas=TEXTURE_ATLAS):
        """
        Creates object that contains data about active chunks \n
        parameters:
            position: 0, 0 for chunks
            texture_atlas: texture atlas object  
            \n

        returns:
            nothing, use object functions for manipulation
        """
        position = pyrr.Vector3(position)
        array_size = ChunkRenderer.ACTIVE_AREA_SIZE.x * ChunkRenderer.ACTIVE_AREA_SIZE.z

        self.VBOs = np.zeros(array_size, int)

        self.chunks = np.zeros(array_size, chunks.Chunk)
        self.start_pos = position
        self.relative_pos = pyrr.Vector3([0, 0, 0])

        # Atlas
        self.texture_atlas = atlas

        # Atlas texture binding
        atlas_texture = glGenTextures(1)
        self.texture_buff = loaders.TextureLoader.load(self.texture_atlas.atlas, atlas_texture)


    def generate_chunks(self):
        for x in ChunkRenderer.ACTIVE_AREA_EDGE:
            for y in ChunkRenderer.ACTIVE_AREA_EDGE:
                chunk = chunks.Chunk(self.texture_atlas.rows, position=(x, 0, y))
                chunk.generate_chunk()
                chunk.generate_mesh(chunk.chunk_data)
                self.add_chunk(chunk)



    def load_chunks_at_position(self, position:tuple[3] or list[3]):
        # unload old chunks
        for chunk in self.chunks:
            if not chunk:
                continue

            self.remove_chunk(chunk)

        # load new chunks
        position = pyrr.Vector3(position) // pyrr.Vector3([16, 64, 16])
        self.relative_pos = position
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = [executor.submit(chunks.load, (i // ChunkRenderer.ACTIVE_AREA_SIZE.x, 0, i % ChunkRenderer.ACTIVE_AREA_SIZE.z), self.texture_atlas.rows) for i, _ in enumerate(self.chunks)]

            for f in concurrent.futures.as_completed(results):
                self.add_chunk(f.result())
            # self.add_chunk(chunks.load((x, 0, z), self.texture_atlas.rows))


    def add_chunk(self, chunk: chunks.Chunk):
        chunk.vertices = chunk.vertices.astype(dtype=np.float32)
        chunk_relative_pos = chunk.position + self.relative_pos
        index = chunk_relative_pos.x * ChunkRenderer.ACTIVE_AREA_SIZE.z + chunk_relative_pos.z

        self.chunks[index] = chunk


    def create_buffers(self):
        """
        Creates buffers for object
        """

        VBO = glGenBuffers(len(self.chunks))

        for i, chunk in enumerate(self.chunks):
            if chunk == 0:
                continue

            # Points Vertex Buffer Object
            glBindBuffer(GL_ARRAY_BUFFER, VBO[i])
            glBufferData(GL_ARRAY_BUFFER, chunk.vertices.nbytes, chunk.vertices, GL_STATIC_DRAW)

            # VBO attribs
            vertex_size = chunk.vertices.itemsize * 6

            # Poisiton
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, vertex_size, ctypes.c_void_p(0))

            # Normal - face index
            glEnableVertexAttribArray(1)
            glVertexAttribPointer(1, 1, GL_FLOAT, GL_FALSE, vertex_size, ctypes.c_void_p(12))

            # Texture offset
            glEnableVertexAttribArray(2)
            glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, vertex_size, ctypes.c_void_p(16))

            self.VBOs[i] = VBO[i]


    def render_all(self, loc_chunk_pos):
        """
        Render object \n
            model_loc: pointer to shader variable
        """
        # print(self.chunks)
        # print(self.VBOs)

        for i, VBO in enumerate(self.VBOs):
            if not VBO:
                continue

            chunk = self.chunks[i]
            glBindBuffer(GL_ARRAY_BUFFER, VBO)

            glUniform3f(loc_chunk_pos, *(self.start_pos + (chunk.position * pyrr.Vector3([16, 0, 16]))))
            glDrawArrays(GL_POINTS, 0, chunk.vertices.nbytes // (4 * 6))



class Object:
    def __init__(self, position: tuple[3] or list[3]=(0, 0, 0), rotation:tuple[3] or list[3]=(0, 0, 0), *args):
        self.transform = Transform(position, rotation)

        for x in args:
            self.add_component(x)

    def add_component(self, component: object):
        name = component.__class__.__name__.lower()
        setattr(self, name, component)

    def remove_component(self, name: str):
        delattr(self, name)



class Camera(Object):
    def __init__(self, fov:int=45, asp_ratio:float=16/9, near_plane: float=0.1, far_plane:int or float=100, position:tuple or list=(0, 2, 3), clamp:tuple or list=(-90, 90), chunk_renderer: ChunkRenderer=None, chunk_offset: tuple[3] or list[3]=(0, 0, 0)):
        """"""
        super().__init__(position, rotation=(-90, 0, 0))
        # yaw = y, pitch = x, roll = z
        self.yaw = -90
        self.pitch = 0

        self.clamp = clamp

        self.up = Vector3.up
        self.front = -Vector3.forward
        self.right = Vector3.right

        self.chunk_renderer = chunk_renderer
        self.chunk_offset = chunk_offset

        # projection matrix
        self.projection = pyrr.matrix44.create_perspective_projection_matrix(fov, asp_ratio, near_plane, far_plane)
        # view matrix
        self.view = pyrr.matrix44.create_look_at(self.transform.position.astype(dtype=np.int32), pyrr.Vector3([0, 0, 0]), pyrr.Vector3([0, 1, 0]))


    def rotate(self, mouse_input: tuple[2] or list[2]):
        yaw = self.yaw
        pitch = self.pitch
        clamp_min, clamp_max = self.clamp
        mouse_x, mouse_y = mouse_input

        # clamp y input between min, max
        pitch = max(clamp_min, min(clamp_max, pitch + mouse_y))
        yaw += mouse_x

        front = pyrr.Vector3([0, 0, 0], dtype=float)
        front.x = cos(radians(yaw)) * cos(radians(pitch))
        front.y = sin(radians(pitch))
        front.z = sin(radians(yaw)) * cos(radians(pitch))

        self.front = vector.normalize(front)
        self.right = vector.normalize(pyrr.vector3.cross(self.front, Vector3.up))
        self.up = vector.normalize(pyrr.vector3.cross(self.right, self.front))

        self.yaw = yaw
        self.pitch = pitch
        
        x = self.transform.position + pyrr.Vector3(self.front)
        self.view = pyrr.matrix44.create_look_at(self.transform.position, x, self.up)


    def raycast(self, ray_length:float=1, player_range:int=8):
        for x in range(player_range):
            raycasted_point = self.transform.position + (x + 1) * ray_length * pyrr.vector.normalize(self.front) - pyrr.Vector3(self.chunk_offset)
            raycasted_chunk_position = raycasted_point // 16
            raycasted_chunk_position.y = 0
            raycasted_block_relative_position = raycasted_point - raycasted_chunk_position * 16

            chunk_index = int(raycasted_chunk_position.x * ChunkRenderer.ACTIVE_AREA_SIZE.z + raycasted_chunk_position.z)
            if chunk_index >= len(self.chunk_renderer.chunks):
                continue
            raycasted_chunk = self.chunk_renderer.chunks[chunk_index]
        
            block_index = int(raycasted_block_relative_position | pyrr.Vector3([1024, 64, 1]))
            if block_index > len(raycasted_chunk.chunk_data):
                continue
            block_type = raycasted_chunk.chunk_data[block_index]

            if block_type:
                return block_type, raycasted_chunk, block_index
            
        return None, None, None



class Player(Object):
    def __init__(self, camera: Camera, sensitivity=0.25, speed=0.15, position:tuple or list=(0, 0, 3), rotation:tuple or list=(0, 0, 0)):
        super().__init__(position, rotation)
        self.sensitivity = sensitivity
        self.speed = speed

        self.camera = camera


    def process_input(self, mouse_input, player_input):
        player_input, self.camera.front, self.speed
        player_input = pyrr.Vector3(player_input)
        player_movement = np.array([0, 0, 0], dtype=float)

        if not player_input.x == 0:
            player_movement += self.camera.right * self.speed * player_input.x
        if not player_input.z == 0:
            player_movement += self.camera.front * self.speed * player_input.z
        if not player_input.y == 0:
            player_movement += Vector3.up * self.speed * player_input.y
            
        mouse_x, mouse_y = mouse_input
        mouse_x *= self.sensitivity
        mouse_y *= -self.sensitivity

        self.camera.transform.move(player_movement)
        self.camera.rotate((mouse_x, mouse_y))
