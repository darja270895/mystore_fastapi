import './App.css'
import AppMain from './components/app-main/AppMain'

// const API = "http://127.0.0.1:8000"

function WhoAmI({name, link}:
                {
                    name: { firstname: string, surname: string };
                    link: string;
                }) {
    return (
        <div className="bio-card-top-right">
            <h3 className="text-sm font-semibold text-gray-900">made by {name.firstname} {name.surname}</h3>
            <a className="text-xs text-gray-500" href={link}>My linkedIn</a>
        </div>
    )
}

// Component. That's a JS function that returns markup.
function App() {

    return (
        // JSX syntaxis
        // Wrap with <div></div> or <> </>
        <div>
            <WhoAmI name={{firstname: 'Daria', surname: 'Harashchenia'}}
                    link="https://www.linkedin.com/in/daria-harashchenia-949081107/"/>
            <AppMain/>
        </div>
    );
}

export default App;
