document.addEventListener("DOMContentLoaded", () => {

    const ctx = document.getElementById("myChart");

    if (ctx) {

        new Chart(ctx, {

            type: 'pie',

            data: {

                labels: [
                    'Excellent',
                    'Good',
                    'Average',
                    'Poor'
                ],

                datasets: [{

                    label: 'Responses',

                    data: [
                        40,
                        25,
                        20,
                        15
                    ]

                }]
            }
        });
    }
});