function setDropdownValue(xName, yName) {
    const select_xlabel = document.getElementById('xlabel');
    console.log(select_xlabel.value);
    console.log(xName);
    select_xlabel.value = xName;
    console.log(select_xlabel.value);
    const select_ylabel = document.getElementById('ylabel');
    select_ylabel.value = yName;
}
