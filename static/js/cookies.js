window.setCookie = function(name, value) {
	var cookie = [
		name,
		'=',
		JSON.stringify(value)
	].join('');
	document.cookie = cookie+';path=/';
}

window.getCookie = function(name) {
	var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    console.log(ca)
	for(var i = 0; i < ca.length; i++) {
		var c = ca[i];
		while (c.charAt(0) == ' ') c = c.substring(1, c.length);
		if (c.indexOf(nameEQ) >= 0) {
			return JSON.parse(
				c.substring(nameEQ.length, c.length)
			);
		}
	}
	return null;
}