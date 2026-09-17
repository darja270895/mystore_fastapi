import PurchasesListItem from './PurchasesListItem'
import type {Purchase} from "./purchases.types";
import {Box, Table} from '@mantine/core'
// import MyButton from "../ui/Button";
// import MyTable from "../ui/Table"

const PurchaseList = ({data}:{data: Purchase[]}) => {

    //array
    const elements = data.map(item => {
        const {id, ...itemProps} = item;
        return (
            <PurchasesListItem key={id} {...itemProps} />// object spread operator
        )
    } )
    console.log(elements)

    return(
        <Box className="dashboard-section">
            <h3>My purchases</h3>
            <Table>
                <Table.Thead>
                    <Table.Tr>
                        <Table.Th>ID</Table.Th>
                        <Table.Th>USER ID</Table.Th>
                        <Table.Th>PRODUCT ID</Table.Th>
                        <Table.Th>AMOUNT</Table.Th>
                        <Table.Th>DATE VALUE</Table.Th>
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {elements}
                </Table.Tbody>

            </Table>
        </Box>
    )
}

export default PurchaseList;