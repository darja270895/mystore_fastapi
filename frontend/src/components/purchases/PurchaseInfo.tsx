// import loadPurchases from "./load_purchases.ts";
// import type {Purchase} from "../../types.ts";
// import {useEffect, useState} from "react";
// import '../../App.css'
//
//
// interface User {
//     id: number;
//     name: string;
//     email: string;
// }
//
//
// function purchasesInfo  ({purchases}) => {
//     const [purchases, setPurchases] = useState<Purchase[]>([]);
//
//     async function handleLoadPurchases() {
//         const purchases = await loadPurchases();
//         console.log(purchases);
//         setPurchases(purchases);
//     }
//
//     useEffect(() => {
//         loadPurchases();
//     }, []);
//
//     return (
//         <section className="dashboard-section">
//             <button className="button" onClick={handleLoadPurchases}>
//                 Refresh
//             </button>
//             <table>
//                 <thead>
//                 <tr>
//                     <th>ID</th>
//                     <th>Name</th>
//                     <th>Email</th>
//                 </tr>
//                 </thead>
//                 <tbody>
//                 {purchases.map((purchase) => (
//                     <tr key={purchase.id}>
//                         <td>{purchase.id}</td>
//                         <td>{purchase.name}</td>
//                         <td>{purchase.email}</td>
//                     </tr>
//                 ))}
//                 </tbody>
//             </table>
//         </section>
//     )
// }
//
// export default purchasesInfo;