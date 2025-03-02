function validateForm(){
    let first_name = document.getElementById("firstName").value;
    let last_name = document.getElementById("lastName").value;
    let email = document.getElementById("email").value;
    let message = document.getElementById("message").value;
        let correct = 1;

    if(first_name == "" || last_name == "" || email == "" || message == ""){
        alert("Some of the required fields are empty");
            correct = 0;
        return false;
    }

    let emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/;
    if(!emailPattern.test(email)){
        alert("Please enter a valid email address");
            correct = 0;
        return false;
    }

        if(correct == 1){
            alert("Succes!");
        }
    return true;
}