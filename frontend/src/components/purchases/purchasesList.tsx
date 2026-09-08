import PurchasesListItem from './PurchasesListItem'
// import {mockPurchases} from "./purchases.mock..ts";

const PurchaseList = ({data}) => {

    //array
    const elements = data.map(item => {
        return (
            <PurchasesListItem
                id={item.id}
                user_id={item.user_id}
                product_id={item.product_id}
                amount={item.amount}
                date_value={item.date_value}
            />
        )
    } )

    return(
        <div>
            <h3 className='dashboard-section h2'>My purchases</h3>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>USER ID</th>
                        <th>PRODUCT ID</th>
                        <th>AMOUNT</th>
                        <th>DATE VALUE</th>
                    </tr>
                </thead>
                <tbody>
                    {elements}
                </tbody>

            </table>
        </div>
    )
}

export default PurchaseList;