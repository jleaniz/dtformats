# -*- coding: utf-8 -*-
"""Binary data format."""

from __future__ import unicode_literals

import abc
import os

from dfdatetime import filetime as dfdatetime_filetime
from dfdatetime import posix_time as dfdatetime_posix_time

from dtfabric import errors as dtfabric_errors
from dtfabric.runtime import data_maps as dtfabric_data_maps
from dtfabric.runtime import fabric as dtfabric_fabric

from dtformats import errors
from dtformats import py2to3


class BinaryDataFormat(object):
  """Binary data format."""

  # The dtFabric definition file, which must be overwritten by a subclass.
  _DEFINITION_FILE = None

  # Preserve the absolute path value of __file__ in case it is changed
  # at run-time.
  _DEFINITION_FILES_PATH = os.path.dirname(__file__)

  _HEXDUMP_CHARACTER_MAP = [
      '.' if byte < 0x20 or byte > 0x7e else chr(byte) for byte in range(256)]

  def __init__(self, debug=False, output_writer=None):
    """Initializes a binary data format.

    Args:
      debug (Optional[bool]): True if debug information should be written.
      output_writer (Optional[OutputWriter]): output writer.
    """
    super(BinaryDataFormat, self).__init__()
    self._data_type_maps = {}
    self._debug = debug
    self._fabric = self._ReadDefinitionFile(self._DEFINITION_FILE)
    self._output_writer = output_writer

  def _DebugPrintData(self, description, data):
    """Prints data for debugging.

    Args:
      description (str): description.
      data (bytes): data.
    """
    if self._output_writer:
      self._output_writer.WriteText('{0:s}:\n'.format(description))
      self._output_writer.WriteText(self._FormatDataInHexadecimal(data))

  def _DebugPrintDecimalValue(self, description, value):
    """Prints a decimal value for debugging.

    Args:
      description (str): description.
      value (int): value.
    """
    value_string = '{0:d}'.format(value)
    self._DebugPrintValue(description, value_string)

  def _DebugPrintFiletimeValue(self, description, value):
    """Prints a FILETIME timestamp value for debugging.

    Args:
      description (str): description.
      value (object): value.
    """
    if value == 0:
      date_time_string = 'Not set (0)'
    elif value == 0x7fffffffffffffff:
      date_time_string = 'Never (0x7fffffffffffffff)'
    else:
      date_time = dfdatetime_filetime.Filetime(timestamp=value)
      date_time_string = date_time.CopyToDateTimeString()
      if date_time_string:
        date_time_string = '{0:s} UTC'.format(date_time_string)
      else:
        date_time_string = '0x{08:x}'.format(value)

    self._DebugPrintValue(description, date_time_string)

  def _DebugPrintStructureObject(self, structure_object, debug_info):
    """Prints structure object debug information.

    Args:
      structure_object (object): structure object.
      debug_info (list[tuple[str, str, int]]): debug information.
    """
    for attribute_name, description, value_format_callback in debug_info:
      attribute_value = getattr(structure_object, attribute_name, None)
      if attribute_value is None:
        continue

      # TODO: remove the need for this exception case.
      if value_format_callback == '_FormatDataInHexadecimal':
        self._DebugPrintData(description, attribute_value)
        continue

      value_format_function = None
      if value_format_callback:
        value_format_function = getattr(self, value_format_callback, None)
      if value_format_function:
        attribute_value = value_format_function(attribute_value)

      self._DebugPrintValue(description, attribute_value)

    self._DebugPrintText('\n')

  def _DebugPrintPosixTimeValue(self, description, value):
    """Prints a POSIX timestamp value for debugging.

    Args:
      description (str): description.
      value (object): value.
    """
    if value == 0:
      date_time_string = 'Not set (0)'
    else:
      date_time = dfdatetime_posix_time.PosixTime(timestamp=value)
      date_time_string = date_time.CopyToDateTimeString()
      if date_time_string:
        date_time_string = '{0:s} UTC'.format(date_time_string)
      else:
        date_time_string = '0x{08:x}'.format(value)

    self._DebugPrintValue(description, date_time_string)

  def _DebugPrintValue(self, description, value):
    """Prints a value for debugging.

    Args:
      description (str): description.
      value (object): value.
    """
    if self._output_writer:
      alignment, _ = divmod(len(description), 8)
      alignment = 8 - alignment + 1
      text = '{0:s}{1:s}: {2!s}\n'.format(
          description, '\t' * alignment, value)
      self._output_writer.WriteText(text)

  def _DebugPrintText(self, text):
    """Prints text for debugging.

    Args:
      text (str): text.
    """
    if self._output_writer:
      self._output_writer.WriteText(text)

  def _FormatDataInHexadecimal(self, data):
    """Formats data in a hexadecimal representation.

    Args:
      data (bytes): data.

    Returns:
      str: hexadecimal representation of the data.
    """
    in_group = False
    previous_hexadecimal_string = None

    lines = []
    data_size = len(data)
    for block_index in range(0, data_size, 16):
      data_string = data[block_index:block_index + 16]

      hexadecimal_byte_values = []
      printable_values = []
      for byte_value in data_string:
        if isinstance(byte_value, py2to3.STRING_TYPES):
          byte_value = ord(byte_value)

        hexadecimal_byte_value = '{0:02x}'.format(byte_value)
        hexadecimal_byte_values.append(hexadecimal_byte_value)

        printable_value = self._HEXDUMP_CHARACTER_MAP[byte_value]
        printable_values.append(printable_value)

      remaining_size = 16 - len(data_string)
      if remaining_size == 0:
        whitespace = ''
      elif remaining_size >= 8:
        whitespace = ' ' * ((3 * remaining_size) - 1)
      else:
        whitespace = ' ' * (3 * remaining_size)

      hexadecimal_string_part1 = ' '.join(hexadecimal_byte_values[0:8])
      hexadecimal_string_part2 = ' '.join(hexadecimal_byte_values[8:16])
      hexadecimal_string = '{0:s}  {1:s}{2:s}'.format(
          hexadecimal_string_part1, hexadecimal_string_part2, whitespace)

      if (previous_hexadecimal_string is not None and
          previous_hexadecimal_string == hexadecimal_string and
          block_index + 16 < data_size):

        if not in_group:
          in_group = True

          lines.append('...')

      else:
        printable_string = ''.join(printable_values)

        lines.append('0x{0:08x}  {1:s}  {2:s}'.format(
            block_index, hexadecimal_string, printable_string))

        in_group = False
        previous_hexadecimal_string = hexadecimal_string

    lines.extend(['', ''])
    return '\n'.join(lines)

  def _FormatArrayOfIntegersAsDecimal(self, array_of_integers):
    """Formats an array of integers as a decimal.

    Args:
      array_of_integers (list[int]): array of integers.

    Returns:
      str: array of integers formatted as decimal.
    """
    return ', '.join(['{0:d}'.format(integer) for integer in array_of_integers])

  def _FormatIntegerAsDecimal(self, integer):
    """Formats an integer as a decimal.

    Args:
      integer (int): integer.

    Returns:
      str: integer formatted as a decimal.
    """
    return '{0:d}'.format(integer)

  def _FormatIntegerAsHexadecimal(self, integer):
    """Formats an integer as a hexadecimal.

    Args:
      integer (int): integer.

    Returns:
      str: integer formatted as a hexadecimal.
    """
    return '0x{0:08x}'.format(integer)

  def _FormatIntegerAsPosixTime(self, integer):
    """Formats an integer as a POSIX date and time value.

    Args:
      integer (int): integer.

    Returns:
      str: integer formatted as decimal.
    """
    if integer == 0:
      return 'Not set (0)'

    date_time = dfdatetime_posix_time.PosixTime(timestamp=integer)
    date_time_string = date_time.CopyToDateTimeString()
    if not date_time_string:
      return '0x{08:x}'.format(integer)

    return '{0:s} UTC'.format(date_time_string)

  def _FormatPackedIPv4Address(self, packed_ip_address):
    """Formats a packed IPv4 address as a human readable string.

    Args:
      packed_ip_address (list[int]): packed IPv4 address.

    Returns:
      str: human readable IPv4 address.
    """
    return '.'.join(['{0:d}'.format(octet) for octet in packed_ip_address[:4]])

  def _FormatPackedIPv6Address(self, packed_ip_address):
    """Formats a packed IPv6 address as a human readable string.

    Args:
      packed_ip_address (list[int]): packed IPv6 address.

    Returns:
      str: human readable IPv6 address.
    """
    # Note that socket.inet_ntop() is not supported on Windows.
    octet_pairs = zip(packed_ip_address[0::2], packed_ip_address[1::2])
    octet_pairs = [octet1 << 8 | octet2 for octet1, octet2 in octet_pairs]
    # TODO: omit ":0000" from the string.
    return ':'.join([
        '{0:04x}'.format(octet_pair) for octet_pair in octet_pairs])

  def _GetDataTypeMap(self, name):
    """Retrieves a data type map defined by the definition file.

    The data type maps are cached for reuse.

    Args:
      name (str): name of the data type as defined by the definition file.

    Returns:
      dtfabric.DataTypeMap: data type map which contains a data type definition,
          such as a structure, that can be mapped onto binary data.
    """
    data_type_map = self._data_type_maps.get(name, None)
    if not data_type_map:
      data_type_map = self._fabric.CreateDataTypeMap(name)
      self._data_type_maps[name] = data_type_map

    return data_type_map

  def _ReadData(self, file_object, file_offset, data_size, description):
    """Reads data.

    Args:
      file_object (file): a file-like object.
      file_offset (int): offset of the data relative to the start of
          the file-like object.
      data_size (int): size of the data.
      description (str): description of the data.

    Returns:
      bytes: byte stream containing the data.

    Raises:
      ParseError: if the data cannot be read.
      ValueError: if the file-like object is missing.
    """
    if not file_object:
      raise ValueError('Missing file-like object.')

    file_object.seek(file_offset, os.SEEK_SET)

    read_error = ''

    try:
      data = file_object.read(data_size)

      if len(data) != data_size:
        read_error = 'missing data'

    except IOError as exception:
      read_error = '{0!s}'.format(exception)

    if read_error:
      raise errors.ParseError((
          'Unable to read {0:s} data at offset: 0x{1:08x} with error: '
          '{2:s}').format(description, file_offset, read_error))

    return data

  def _ReadDefinitionFile(self, filename):
    """Reads a dtFabric definition file.

    Args:
      filename (str): name of the dtFabric definition file.

    Returns:
      dtfabric.DataTypeFabric: data type fabric which contains the data format
          data type maps of the data type definition, such as a structure, that
          can be mapped onto binary data or None if no filename is provided.
    """
    if not filename:
      return None

    path = os.path.join(self._DEFINITION_FILES_PATH, filename)
    with open(path, 'rb') as file_object:
      definition = file_object.read()

    return dtfabric_fabric.DataTypeFabric(yaml_definition=definition)

  # TODO: deprecate in favor of _ReadStructureFromFileObject
  def _ReadStructure(
      self, file_object, file_offset, data_size, data_type_map, description):
    """Reads a structure.

    Args:
      file_object (file): a file-like object.
      file_offset (int): offset of the structure data relative to the start
          of the file-like object.
      data_size (int): data size of the structure.
      data_type_map (dtfabric.DataTypeMap): data type map of the structure.
      description (str): description of the structure.

    Returns:
      object: structure values object.

    Raises:
      ParseError: if the structure cannot be read.
      ValueError: if file-like object or data type map is missing.
    """
    if self._debug:
      self._DebugPrintText('Reading {0:s} at offset: 0x{1:08x}\n'.format(
          description, file_offset))

    data = self._ReadData(file_object, file_offset, data_size, description)

    if self._debug:
      data_description = '{0:s} data'.format(description.title())
      self._DebugPrintData(data_description, data)

    return self._ReadStructureFromByteStream(
        data, file_offset, data_type_map, description)

  def _ReadStructureFromByteStream(
      self, byte_stream, file_offset, data_type_map, description, context=None):
    """Reads a structure from a byte stream.

    Args:
      byte_stream (bytes): byte stream.
      file_offset (int): offset of the structure data relative to the start
          of the file-like object.
      data_type_map (dtfabric.DataTypeMap): data type map of the structure.
      description (str): description of the structure.
      context (Optional[dtfabric.DataTypeMapContext]): data type map context.
      suppress_debug_output (Optional[bool]): True if debug output should be
          suppressed.

    Returns:
      object: structure values object.

    Raises:
      ParseError: if the structure cannot be read.
      ValueError: if file-like object or data type map is missing.
    """
    if not byte_stream:
      raise ValueError('Missing byte stream.')

    if not data_type_map:
      raise ValueError('Missing data type map.')

    try:
      return data_type_map.MapByteStream(byte_stream, context=context)
    except (dtfabric_errors.ByteStreamTooSmallError,
            dtfabric_errors.MappingError) as exception:
      raise errors.ParseError((
          'Unable to map {0:s} data at offset: 0x{1:08x} with error: '
          '{2!s}').format(description, file_offset, exception))

  def _ReadStructureFromFileObject(
      self, file_object, file_offset, data_type_map, description):
    """Reads a structure from a file-like object.

    If the data type map has a fixed size this method will read the predefined
    number of bytes from the file-like object. If the data type map has a
    variable size, depending on values in the byte stream, this method will
    continue to read from the file-like object until the data type map can be
    successfully mapped onto the byte stream or until an error occurs.

    Args:
      file_object (dvfvs.FileIO): a file-like object to parse.
      file_offset (int): offset of the structure data relative to the start
          of the file-like object.
      data_type_map (dtfabric.DataTypeMap): data type map of the structure.
      description (str): description of the structure.

    Returns:
      tuple[object, int]: structure values object and data size of
          the structure.

    Raises:
      ParseError: if the structure cannot be read.
      ValueError: if file-like object or data type map is missing.
    """
    context = None
    last_data_size = 0

    data_size = data_type_map.GetByteSize()
    if not data_size:
      data_size = data_type_map.GetSizeHint()

    if self._debug:
      self._DebugPrintText('Reading {0:s} at offset: 0x{1:08x}\n'.format(
          description, file_offset))

    while data_size != last_data_size:
      data = self._ReadData(file_object, file_offset, data_size, description)

      try:
        context = dtfabric_data_maps.DataTypeMapContext()
        structure_values_object = data_type_map.MapByteStream(
            data, context=context)

        if self._debug:
          data_description = '{0:s} data'.format(description.title())
          self._DebugPrintData(data_description, data)

        return structure_values_object, data_size

      except dtfabric_errors.ByteStreamTooSmallError:
        pass

      except dtfabric_errors.MappingError as exception:
        raise errors.ParseError((
            'Unable to map {0:s} data at offset: 0x{1:08x} with error: '
            '{2!s}').format(description, file_offset, exception))

      last_data_size = data_size
      data_size = data_type_map.GetSizeHint(context=context)

    raise errors.ParseError(
        'Unable to read {0:s} at offset: 0x{1:08x}'.format(
            description, file_offset))


class BinaryDataFile(BinaryDataFormat):
  """Binary data file."""

  def __init__(self, debug=False, output_writer=None):
    """Initializes a binary data file.

    Args:
      debug (Optional[bool]): True if debug information should be written.
      output_writer (Optional[OutputWriter]): output writer.
    """
    super(BinaryDataFile, self).__init__(
        debug=debug, output_writer=output_writer)
    self._file_object = None
    self._file_object_opened_in_object = False
    self._file_size = 0
    self._path = None

  def Close(self):
    """Closes a binary data file.

    Raises:
      IOError: if the file is not opened.
    """
    if not self._file_object:
      raise IOError('File not opened')

    if self._file_object_opened_in_object:
      self._file_object.close()
      self._file_object_opened_in_object = False
    self._file_object = None
    self._path = None

  def Open(self, path):
    """Opens a binary data file.

    Args:
      path (str): path to the file.

    Raises:
      IOError: if the file is already opened.
    """
    if self._file_object:
      raise IOError('File already opened')

    stat_object = os.stat(path)

    file_object = open(path, 'rb')

    self._file_size = stat_object.st_size
    self._path = path

    self.ReadFileObject(file_object)

    self._file_object = file_object
    self._file_object_opened_in_object = True

  @abc.abstractmethod
  def ReadFileObject(self, file_object):
    """Reads binary data from a file-like object.

    Args:
      file_object (file): file-like object.
    """
