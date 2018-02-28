(function(){
    // update button
    var formatDate = function (date) {
        var padNumber = function(num, wide){ return ("0000" + num).slice(-wide);};
        return (
            padNumber(date.getMinutes(), 2) +
            ":" +
            padNumber(date.getSeconds(), 2) +
            "." +
            padNumber((date.getMilliseconds()/100)|0, 1)
        );
    };
    $update = $("#updateButton");
    var buttonText = $update.text();
    var timeToCountDown = (1000*60*1.5)|0; /*ms*/
    var countDownFrequency = 100; /*ms*/
    var countdown = new Date(0);
    countdown.setMilliseconds(timeToCountDown);
    setInterval(function (){
        $update.text(buttonText + " (" + formatDate(countdown) + ")");
        countdown.setMilliseconds(countdown.getMilliseconds() - countDownFrequency);
    }, countDownFrequency);
    setInterval(function (){
        countdown = new Date(0);
        countdown.setMilliseconds(timeToCountDown);
        $update.click();
    }, timeToCountDown);

    // "start" website
    resetProperties();
    updateDataAndShow();
})();

function updateDataAndShow() {
    $.getJSON("/db", function (data) {
        window.myJsonData = data;
        window.myJsonDataUsers = Object.keys(data).sort();
        createGanttDiagram();
    });
}

function getLabelData(rawData) {
    var properties = window.currentProperties;
    var states = ["online", "active", "mobile"];
    var users = Object.keys(rawData).sort();
    var epochMin = 0;
    var epochMax = 1e12;
    if (properties.states.length != 0){
        states = properties.states;
    }
    if (properties.users.length != 0){
        users = properties.users;
    }
    if (properties.from != null){
        epochMin = properties.from;
    }
    if (properties.to != null){
        epochMax = properties.to;
    }
    var labelData = [];
    for (var user of users) {
        for (var state of states) {
            var userStateTimes = [];
            for (var interval of rawData[user][state]) {
                if (interval[0] >= epochMin && interval[1] <= epochMax){
                    userStateTimes.push({
                            "starting_time": (interval[0] - 3600) * 1000,
                            "ending_time": (interval[1] - 3600) * 1000
                    });
                }
            }
            if (userStateTimes.length != 0) {
                labelData.push({
                    color: state,
                    label: rawData[user]["fullname"] + " "  + ["","👁","📱"][states.indexOf(state)],
                    icon: "data:image/png;base64," + rawData[user].image,
                    times: userStateTimes
                });
            }
        }
    }
    return labelData;
}

function createGanttDiagram() {
    var labelData = getLabelData(myJsonData);
    var colorScale = d3.scale.ordinal().range(['#999', '#2b0', '#59f'])
        .domain(['online', 'active', 'mobile']);
    var width = (window.innerWidth * .9) | 0;
    var chart = d3.timeline()
        .width(width)
        .stack()
        .margin({left: 250, right: 0, top: 20, bottom: 0})
        .itemMargin(5)
        .labelMargin(25)
        .showTimeAxisTick()
        .showAxisTop()
        .colors(colorScale)
        .colorProperty('color')
        .background(function (datum, i) {
            return "#def";
        })
        .tickFormat({
            format: d3.time.format(currentProperties.tickFormat),
            tickTime: d3.time[currentProperties.tickType],
            tickInterval: currentProperties.tickFreq,
            tickSize: 6,
            tickValues: null
        })
        .fullLengthBackgrounds()
        .hover(function (d, i, datum) {
            // d is the current rendering object
            // i is the index during d3 rendering
            // datum is the id object
            var tooltip = $("#tooltip");
            tooltip.show();
            var from = new Date(d.starting_time);
            var to = new Date(d.ending_time);
            var fromFMT = from.toISOString().replace(/[TZ]/g," ").slice(0,-5)
            var toFMT = to.toISOString().replace(/[TZ]/g," ").slice(0,-5)
            tooltip.text(fromFMT + " → " + toFMT);
            tooltip.offset({ top: window.event.clientY - tooltip.height() - 5, left: window.event.clientX});
        })
        .mouseout(function () {
            $("#tooltip").hide();
        })
        /*.click(function (d, i, datum) {
            alert(datum.label);
        })*/
        /*.scroll(function (x, scale) {
            $("#scrolled_date").text(scale.invert(x) + " to " + scale.invert(x + width));
        })*/;

    // remove old svg content if exists
    if ($("#timelineComplex > svg").length != 0){
        d3.select("#timelineComplex").select("svg").selectAll("*").remove();
        d3.select("#timelineComplex").select("svg").attr("width", width).datum(labelData).call(chart);
    } else {
        d3.select("#timelineComplex").append("svg").attr("width", width).datum(labelData).call(chart);
    }
}

function resetProperties() {
    window.currentProperties = {
        states: [],
        users: [],
        from: null,
        to: null,
        tickFormat: "%a. %H:%M",
        tickType: "hours",
        tickFreq: 6
    };
}

function resetFilterAction() {
    resetProperties();
    createGanttDiagram();
}

function filterDataAction() {
    // get data view
    var online = $("#inlineCheckbox1").prop('checked');
    var active = $("#inlineCheckbox2").prop('checked');
    var mobile = $("#inlineCheckbox3").prop('checked');
    var regexText = $("#exampleInputName2").val();
    var epochStart = 0 + $("#example-number-input").val();
    if (epochStart == 0){
        epochStart = null;
    }
    var epochEnd = 0 + $("#example-number-input2").val();
    if (epochEnd == 0){
        epochEnd = null;
    }
    var states = [];
    if (online) states.push("online");
    if (active) states.push("active");
    if (mobile) states.push("mobile");
    var users = myJsonDataUsers.filter(function(userName){
        return new RegExp(regexText, "g").test(userName);
    });

    // get view settings
    var propArray = [
        "checkbox-year",
        "checkbox-month",
        "checkbox-day",
        "checkbox-weekday",
        "checkbox-hour",
        "checkbox-minute"
    ];
    var tickFormat = "";
    for (var idStr of propArray){
        var $cb = $("#" + idStr);
        if ($cb.prop("checked")){
            tickFormat += $cb.val();
        }
    }
    var tickType = $("input[id*=exampleRadios1]:checked").first().val();
    var checkedRadioType = tickType.substring(0, tickType.length-1);
    var inputValue = $("#" + checkedRadioType + "-input").first().val();
    var tickFreq = 1;
    if (inputValue.length != 0){
        tickFreq = parseInt(inputValue);
    }
    window.currentProperties = {
        states: states,
        users: users,
        from: epochStart,
        to: epochEnd,
        tickFormat: tickFormat,
        tickType: tickType,
        tickFreq: tickFreq
    };
    createGanttDiagram();
}