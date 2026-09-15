import '@mantine/core/styles.css';
import {Table} from '@mantine/core'


interface TableProps {
    data: Record<string, unknown>[];
}
export default function MyTable({data}: TableProps) {
    if (!data.length) {
        return null;
    }
    const columns = Object.keys(data[0]);

    return (
        <Table.ScrollContainer minWidth={500} type="native">
            <Table>
                <Table.Thead>
                    <Table.Tr>
                        {columns.map((column) =>
                        <Table.Th key={column}>{column}</Table.Th>
                        )}
                    </Table.Tr>
                </Table.Thead>

                <Table.Tbody>
                    {data.map((row, rowIndex) =>
                    <Table.Tr key={rowIndex}>
                        {columns.map((column) =>
                        <Table.Td key={column}>
                            {String(row[column] ?? '')}
                        </Table.Td>
                        )}
                    </Table.Tr>
                    )}
                </Table.Tbody>
            </Table>
        </Table.ScrollContainer>
    );
}