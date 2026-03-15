export interface ZipFileInput {
    name: string;
    content: string;
}

const textEncoder = new TextEncoder();
const zipSignature = {
    localFileHeader: 0x04034b50,
    centralDirectoryHeader: 0x02014b50,
    endOfCentralDirectory: 0x06054b50,
};

function buildCrcTable(): Uint32Array {
    const table = new Uint32Array(256);
    for (let index = 0; index < 256; index += 1) {
        let value = index;
        for (let bit = 0; bit < 8; bit += 1) {
            value = (value & 1) !== 0 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
        }
        table[index] = value >>> 0;
    }
    return table;
}

const crcTable = buildCrcTable();

function crc32(bytes: Uint8Array): number {
    let crc = 0xffffffff;
    for (const byte of bytes) {
        crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
}

function toDosTimestamp(value = new Date()): {date: number; time: number} {
    const year = Math.max(value.getFullYear(), 1980);
    return {
        time:
            ((value.getHours() & 0x1f) << 11) |
            ((value.getMinutes() & 0x3f) << 5) |
            Math.floor(value.getSeconds() / 2),
        date:
            (((year - 1980) & 0x7f) << 9) |
            (((value.getMonth() + 1) & 0x0f) << 5) |
            (value.getDate() & 0x1f),
    };
}

function createLocalHeader(
    nameLength: number,
    size: number,
    checksum: number,
    timestamp: {date: number; time: number},
): Uint8Array {
    const header = new Uint8Array(30);
    const view = new DataView(header.buffer);
    view.setUint32(0, zipSignature.localFileHeader, true);
    view.setUint16(4, 20, true);
    view.setUint16(6, 0, true);
    view.setUint16(8, 0, true);
    view.setUint16(10, timestamp.time, true);
    view.setUint16(12, timestamp.date, true);
    view.setUint32(14, checksum, true);
    view.setUint32(18, size, true);
    view.setUint32(22, size, true);
    view.setUint16(26, nameLength, true);
    view.setUint16(28, 0, true);
    return header;
}

function createCentralHeader(
    nameLength: number,
    size: number,
    checksum: number,
    timestamp: {date: number; time: number},
    localHeaderOffset: number,
): Uint8Array {
    const header = new Uint8Array(46);
    const view = new DataView(header.buffer);
    view.setUint32(0, zipSignature.centralDirectoryHeader, true);
    view.setUint16(4, 20, true);
    view.setUint16(6, 20, true);
    view.setUint16(8, 0, true);
    view.setUint16(10, 0, true);
    view.setUint16(12, timestamp.time, true);
    view.setUint16(14, timestamp.date, true);
    view.setUint32(16, checksum, true);
    view.setUint32(20, size, true);
    view.setUint32(24, size, true);
    view.setUint16(28, nameLength, true);
    view.setUint16(30, 0, true);
    view.setUint16(32, 0, true);
    view.setUint16(34, 0, true);
    view.setUint16(36, 0, true);
    view.setUint32(38, 0, true);
    view.setUint32(42, localHeaderOffset, true);
    return header;
}

function createEndRecord(
    fileCount: number,
    centralDirectorySize: number,
    centralDirectoryOffset: number,
): Uint8Array {
    const footer = new Uint8Array(22);
    const view = new DataView(footer.buffer);
    view.setUint32(0, zipSignature.endOfCentralDirectory, true);
    view.setUint16(4, 0, true);
    view.setUint16(6, 0, true);
    view.setUint16(8, fileCount, true);
    view.setUint16(10, fileCount, true);
    view.setUint32(12, centralDirectorySize, true);
    view.setUint32(16, centralDirectoryOffset, true);
    view.setUint16(20, 0, true);
    return footer;
}

function joinChunks(chunks: Uint8Array[]): Uint8Array {
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
    const archive = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
        archive.set(chunk, offset);
        offset += chunk.byteLength;
    }
    return archive;
}

export function createZipBlob(files: ZipFileInput[]): Blob {
    const chunks: Uint8Array[] = [];
    const centralChunks: Uint8Array[] = [];
    const timestamp = toDosTimestamp();
    let offset = 0;

    for (const file of files) {
        const nameBytes = textEncoder.encode(file.name);
        const contentBytes = textEncoder.encode(file.content);
        const checksum = crc32(contentBytes);
        const localHeader = createLocalHeader(
            nameBytes.byteLength,
            contentBytes.byteLength,
            checksum,
            timestamp,
        );
        const centralHeader = createCentralHeader(
            nameBytes.byteLength,
            contentBytes.byteLength,
            checksum,
            timestamp,
            offset,
        );

        chunks.push(localHeader, nameBytes, contentBytes);
        centralChunks.push(centralHeader, nameBytes);
        offset += localHeader.byteLength + nameBytes.byteLength + contentBytes.byteLength;
    }

    const centralDirectory = joinChunks(centralChunks);
    const footer = createEndRecord(
        files.length,
        centralDirectory.byteLength,
        offset,
    );
    const archive = joinChunks([...chunks, centralDirectory, footer]);
    const zipBytes = new Uint8Array(archive.byteLength);
    zipBytes.set(archive);
    return new Blob([zipBytes.buffer as ArrayBuffer], {type: "application/zip"});
}
