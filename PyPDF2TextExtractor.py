#!/usr/bin/env python3
from PyPDF2.pdf import ContentStream


class ContentOperation(object):
    def __init__(self):
        self.name = self.__class__.__name__

    def __repr__(self):
        return self.name


# Operations not otherwise caught/handled
class GenericOperation(ContentOperation):
    seenOperations = set()

    def __init__(self, operation, operands):
        ContentOperation.__init__(self)
        self.operation = operation
        self.operands = operands
        GenericOperation.seenOperations.add(operation)

    def __repr__(self):
        return "{}: {}".format(self.operation, self.operands)


# Simple Operations, just consume their operands
class PushState(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        assert len(operands) == 0


class PopState(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        assert len(operands) == 0


class StrokePath(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        assert len(operands) == 0


class FillPath(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        assert len(operands) == 0


class CloseSubPath(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        assert len(operands) == 0


class XObject(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        self.objName, = operands

    def __repr__(self):
        return "{}: {}".format(self.name, self.objName)


class AddRectanglePath(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        x, y, self.width, self.height = operands
        self.position = (x, y)

    def __repr__(self):
        return "{}: {} {} x {}".format(self.name, self.position, self.width,
                                       self.height)


class NewSubPath(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        assert len(operands) == 2
        self.position = tuple(operands)

    def __repr__(self):
        return "{}: {}".format(self.name, self.position)


class LineSegment(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        assert len(operands) == 2
        self.position = tuple(operands)

    def __repr__(self):
        return "{}: {}".format(self.name, self.position)


class StrokingColourSpaceGray(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        self.grayLevel, = operands
        assert self.grayLevel >= 0.0
        assert self.grayLevel <= 1.0

    def __repr__(self):
        return "{}: {}".format(self.name, self.grayLevel)


class NonStrokingColourSpaceGray(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        self.grayLevel, = operands
        assert self.grayLevel >= 0.0
        assert self.grayLevel <= 1.0

    def __repr__(self):
        return "{}: {}".format(self.name, self.grayLevel)


class LineWidth(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        self.lineWidth, = operands
        assert self.lineWidth >= 0.0

    def __repr__(self):
        return "{}: {}".format(self.name, self.lineWidth)


class LineDashPattern(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        self.dashArray, self.dashPhase = operands

    def __repr__(self):
        return "{}: {}, {}".format(self.name, self.dashArray, self.dashPhase)


class TextWidth(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        self.wordSpace, = operands

    def __repr__(self):
        return "{}: {}".format(self.name, self.wordSpace)


class TextCharSpace(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        self.charSpace, = operands

    def __repr__(self):
        return "{}: {}".format(self.name, self.charSpace)


class TextRenderMode(ContentOperation):
    def __init__(self, operands):
        ContentOperation.__init__(self)
        self.renderMode, = operands

    def __repr__(self):
        return "{}: {}".format(self.name, self.renderMode)


class ConcatenateTransformationMatrix(ContentOperation):
    """
    Premultiplies the given matrix with the existing transformation matrix.
    The matrix is
    [ [a b 0 ] ]
    [ [c d 0 ] ]
    [ [e f 1 ] ]
    """

    def __init__(self, operands):
        ContentOperation.__init__(self)
        assert len(operands) == 6
        self.matrixChange = [
            [float(operands[0]), float(operands[1]), 0.0],
            [float(operands[2]), float(operands[3]), 0.0],
            [float(operands[4]), float(operands[5]), 1.0],
        ]

    def __repr__(self):
        return "{}: {}".format(self.name, self.matrixChange)


simpleObjects = {
    b"q": PushState,
    b"Q": PopState,
    b"Do": XObject,
    b"m": NewSubPath,
    b"l": LineSegment,
    b"G": StrokingColourSpaceGray,
    b"g": NonStrokingColourSpaceGray,
    b"w": LineWidth,
    b"S": StrokePath,
    b"f": FillPath,
    b"h": CloseSubPath,
    b"cm": ConcatenateTransformationMatrix,
    b"d": LineDashPattern,
    b"re": AddRectanglePath,
    b"Tw": TextWidth,
    b"Tr": TextRenderMode,
    b"Tc": TextCharSpace,
}


# Special-case Operations, defining an object with a series of operations
class TextObject(ContentOperation):
    def __init__(self, operations):
        ContentOperation.__init__(self)
        # An array of tuples (text-space, text)
        self.outputs = []

        linePos = [0, 0]
        for operation, operands in operations:
            if operation == b"Td":
                assert len(operands) == 2
                linePos[0] += operands[0]
                linePos[1] += operands[1]
            elif operation in (b"Tj", b"TJ"):
                # TJ is Tj with embedded spacing-adjustments
                assert len(operands) == 1
                if len(self.outputs) > 0:
                    assert self.outputs[-1][0] != tuple(linePos)
                self.outputs.append((tuple(linePos), operands[0]))
            elif operation == b"Tm":
                assert len(operands) == 6
                # Scaling and translation
                assert operands[1] == 0
                assert operands[2] == 0
                # TODO: Scaling shouldn't affect the translation, I hope.
                #print(("Scaling to ({},{})".format(operands[0], operands[3])))
                linePos = [operands[4], operands[5]]
            elif operation == b"Tf":
                pass  # Font change
            else:
                assert False, "Unexpected operation {}: {}".format(operation,
                                                                   operands)

    def __repr__(self):
        return "TextObject: {}".format(self.outputs)


def pageOperations(page):
    obj = page.getContents().getObject()
    # Trigger decoding
    obj.getData()
    content = ContentStream(obj.decodedSelf, page.pdf)
    return contentOperations(content)


def contentOperations(content):
    index = 0
    count = len(content.operations)
    while index < count:
        operands, operation = content.operations[index]
        index += 1

        # BT operator introduces a TextObject
        if operation == b"BT":
            textObjectOps = []
            while index < count:
                operands, operation = content.operations[index]
                index += 1

                if operation == b"ET":
                    yield TextObject(textObjectOps)
                    break

                assert index != count, "Hit the last operation: '{}' while inside a TextObject".format(
                    operation)

                textObjectOps.append((operation, operands))
        elif operation in list(simpleObjects.keys()):
            yield simpleObjects[operation](operands)
        else:
            # Generic/Unhandled Operations
            yield GenericOperation(operation, operands)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("statement")
    args = parser.parse_args()

    from PyPDF2 import PdfFileReader
    x = PdfFileReader(open(args.statement, 'rb'))
    print((x.getNumPages()))
    page1 = x.getPage(0)

    print(("\n".join([str(e)
                      for e in pageOperations(x.getPage(0))
                      if e.__class__ is not TextObject])))
    print(("\n".join([str(e)
                      for e in pageOperations(x.getPage(1))
                      if e.__class__ is not TextObject])))
    assert len(
        GenericOperation.seenOperations) == 0, "Unknown operations in PDF: {}".format(
            GenericOperation.seenOperations)
