var benchSelected = false;
var modelSelected = false

var coll_model = document.getElementsByClassName("model_checker");
var coll_benchmark = document.getElementsByClassName("benchmark_checker");
var i;

for (i = 0; i < coll_model.length; i++) {
    coll_model[i].onchange = function() {enableButtonModel()}
}
for (i = 0; i < coll_benchmark.length; i++) {
    coll_benchmark[i].onchange = function() {enableButtonBench()}
}

function enableButtonBench(){
    benchSelected = true
    if(benchSelected && modelSelected){
        enableSubmit()
    }
}

function enableButtonModel(){
    modelSelected = true
    if (benchSelected && modelSelected) {
        enableSubmit()
    }
}

function enableSubmit(){
    document.getElementById('resubmit').disabled = false;
}